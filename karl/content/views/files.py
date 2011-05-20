# Copyright (C) 2008-2009 Open Society Institute
#               Thomas Moroz: tmoroz@sorosny.org
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License Version 2 as published
# by the Free Software Foundation.  You may not use, modify or distribute
# this program under any other version of the GNU General Public License.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

from simplejson import JSONEncoder
from simplejson import JSONDecoder
import datetime
import transaction
from karl.log import get_logger

import formish
import schemaish
from schemaish.type import File as SchemaFile
from validatish import validator

from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter
from zope.component.event import objectEventNotify
from zope.component import queryUtility
from zope.interface import alsoProvides
from zope.interface import noLongerProvides

from webob import Response
from webob.exc import HTTPFound

from repoze.bfg.chameleon_zpt import render_template_to_response
from repoze.bfg.traversal import find_interface
from repoze.bfg.traversal import model_path

from repoze.bfg.security import authenticated_userid
from repoze.bfg.security import has_permission
from repoze.bfg.url import model_url
from repoze.workflow import get_workflow
from repoze.bfg.formish import ValidationError

from repoze.lemonade.content import create_content

from karl.utilities.alerts import Alerts
from karl.utilities.interfaces import IAlerts

from karl.views.utils import make_name
from karl.views.utils import make_unique_name
from karl.views.utils import basename_of_filepath
from karl.views.utils import convert_to_script
from karl.views.tags import get_tags_client_data
from karl.views.forms import widgets as karlwidgets

from karl.views.api import TemplateAPI
from karl.views.resource import delete_resource_view

from karl.events import ObjectModifiedEvent
from karl.events import ObjectWillBeModifiedEvent

from karl.content.interfaces import ICommunityFile
from karl.content.interfaces import ICommunityFolder
from karl.content.interfaces import ICommunityRootFolder
from karl.content.interfaces import IImage
from karl.content.interfaces import IIntranetRootFolder
from karl.content.interfaces import IIntranets

from karl.content.views.interfaces import IFileInfo
from karl.content.views.interfaces import IFolderCustomizer
from karl.content.views.interfaces import INetworkNewsMarker
from karl.content.views.interfaces import INetworkEventsMarker

from karl.content.interfaces import IReferencesFolder

from karl.models.interfaces import ICatalogSearch
from karl.utils import find_catalog

# This import is BBB for karl.evolve.zodb.evolve15
from karl.content.views.utils import ie_types

from karl.content.views.utils import get_upload_mimetype
from karl.content.views.utils import get_previous_next
from karl.content.views.utils import get_show_sendalert

from karl.security.workflow import get_security_states

from karl.utils import find_community
from karl.utils import get_folder_addables
from karl.utils import get_layout_provider
from karl.utils import find_tempfolder

from karl.views.tags import set_tags
from karl.views.batch import get_container_batch

from karl.views.utils import check_upload_size

from karl.views.forms.filestore import get_filestore

log = get_logger()

def show_folder_view(context, request):
    
    page_title = context.title
    api = TemplateAPI(context, request, page_title)

    # Now get the data that goes with this


    # Actions
    backto = False
    actions = []
    if has_permission('create', context, request):
        # Allow "policy" to override list of addables in a particular context
        addables = get_folder_addables(context, request)
        if addables is not None:
            actions.extend(addables())

    if not (ICommunityRootFolder.providedBy(context) or
        IIntranetRootFolder.providedBy(context)):
        # Root folders for the tools aren't editable or deletable
        if has_permission('edit', context, request):
            actions.append(('Edit', 'edit.html'))

        if has_permission('delete', context.__parent__, request):
            actions.append(('Delete', 'delete.html'))

        in_intranets = find_interface(context, IIntranets) is not None
        if has_permission('administer', context, request) and in_intranets:
            # admins see an Advanced action that puts markers on a
            # folder.
            actions.append(
                ('Advanced','advanced.html'),
                )
        backto = {
            'href': model_url(context.__parent__, request),
            'title': context.__parent__.title,
            }

    # Only provide atom feed links on root folder.
    if ICommunityRootFolder.providedBy(context):
        feed_url = model_url(context, request, "atom.xml")
    else:
        feed_url = None

    # Folder and tag data for Ajax
    client_json_data = dict(
        filegrid = get_filegrid_client_data(context, request,
                                            start = 0,
                                            limit = 10,
                                            sort_on = 'modified_date',
                                            reverse = True,
                                            ),
        tagbox = get_tags_client_data(context, request),
        )

    # Get a layout
    layout_provider = get_layout_provider(context, request)
    layout = layout_provider('community')

    return dict(
        api=api,
        actions=actions,
        head_data=convert_to_script(client_json_data),
        backto=backto,
        layout=layout,
        feed_url=feed_url,
        )


def redirect_to_add_form(context, request):
    return HTTPFound(
            location=model_url(context, request, 'add_file.html'))

title_field = schemaish.String(
    validator=validator.All(
        validator.Length(max=100),
        validator.Required(),
        )
    )
tags_field = schemaish.Sequence(schemaish.String())
security_field = schemaish.String(
    description=('Items marked as private can only be seen by '
                 'members of this community.'))
sendalert_field = schemaish.Boolean(
    title='Send email alert to community members?')
file_field = schemaish.File(
    title='File',
    validator=validator.Required(),
    description='You can replace the file by clicking "remove"',
    )

class AddFolderFormController(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.workflow = get_workflow(ICommunityFolder, 'security', context)

    def _get_security_states(self):
        return get_security_states(self.workflow, None, self.request)

    def form_defaults(self):
        defaults = {
            'title':'',
            'tags':[],
            }

        if self.workflow is not None:
            defaults['security_state'] = self.workflow.initial_state
        return defaults

    def form_fields(self):
        fields = []
        fields.append(('title', title_field))
        fields.append(('tags', tags_field))
        security_states = self._get_security_states()
        if security_states:
            fields.append(('security_state', security_field))
        return fields

    def form_widgets(self, fields):
        widgets = {
            'title':formish.Input(empty=''),
            'tags':karlwidgets.TagsAddWidget(),
            }
        security_states = self._get_security_states()
        schema = dict(fields)
        if 'security_state' in schema:
            security_states = self._get_security_states()
            widgets['security_state'] = formish.RadioChoice(
                options=[ (s['name'], s['title']) for s in security_states],
                none_option=None)
        return widgets

    def __call__(self):
        api = TemplateAPI(self.context, self.request, 'Add Folder')
        layout_provider = get_layout_provider(self.context, self.request)
        if layout_provider is None:
            layout = api.community_layout
        else:
            layout = layout_provider('community')
        return {'api':api, 'actions':(), 'layout':layout}

    def handle_cancel(self):
        return HTTPFound(location=model_url(self.context, self.request))

    def handle_submit(self, converted):
        context = self.context
        request = self.request
        workflow = self.workflow

        name = make_unique_name(context, converted['title'])
        creator = authenticated_userid(request)

        folder = create_content(ICommunityFolder,
                                converted['title'],
                                creator,
                                )
        context[name] = folder
        if workflow is not None:
            workflow.initialize(folder)
            if 'security_state' in converted:
                workflow.transition_to_state(folder, request,
                                             converted['security_state'])

        # Tags, attachments, alerts
        set_tags(folder, request, converted['tags'])

        # Make changes post-creation based on policy in src/osi
        customizer = queryMultiAdapter((folder, request), IFolderCustomizer)
        if customizer:
            for interface in customizer.markers:
                alsoProvides(folder, interface)

        location = model_url(folder, request)
        return HTTPFound(location=location)

def delete_folder_view(context, request,
                       delete_resource_view=delete_resource_view):
    # delete_resource_view is passed as hook for unit testing
    return delete_resource_view(context, request, len(context))

def advanced_folder_view(context, request):

    page_title = 'Advanced Settings For ' + context.title
    api = TemplateAPI(context, request, page_title)

    if 'form.cancel' in request.POST:
        return HTTPFound(location=model_url(context, request))

    if 'form.submitted' in request.POST:
        marker = request.POST.get('marker', False)
        if marker == 'reference_manual':
            alsoProvides(context, IReferencesFolder)
            noLongerProvides(context, INetworkNewsMarker)
            noLongerProvides(context, INetworkEventsMarker)
        elif marker == 'network_news':
            alsoProvides(context, INetworkNewsMarker)
            noLongerProvides(context, IReferencesFolder)
            noLongerProvides(context, INetworkEventsMarker)
        elif marker == 'network_events':
            alsoProvides(context, INetworkEventsMarker)
            noLongerProvides(context, IReferencesFolder)
            noLongerProvides(context, INetworkNewsMarker)

        if marker:
            location = model_url(context, request, query=
                                 {'status_message': 'Marker changed'})
            return HTTPFound(location=location)

    # Get a layout
    layout_provider = get_layout_provider(context, request)
    layout = layout_provider('community')

    if IReferencesFolder.providedBy(context):
        selected = 'reference_manual'
    elif INetworkNewsMarker.providedBy(context):
        selected = 'network_news'
    elif INetworkEventsMarker.providedBy(context):
        selected = 'network_events'
    else:
        selected = None

    return render_template_to_response(
        'templates/advanced_folder.pt',
        api=api,
        actions=[],
        formfields=api.formfields,
        post_url=model_url(context, request, 'advanced.html'),
        layout=layout,
        fielderrors={},
        selected=selected,
        )


class AddFileFormController(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.workflow = get_workflow(ICommunityFile, 'security', context)
        self.filestore = get_filestore(context, request, 'add-file')
        self.show_sendalert = get_show_sendalert(self.context, self.request)
        self.check_upload_size = check_upload_size # for testing

    def _get_security_states(self):
        return get_security_states(self.workflow, None, self.request)

    def form_defaults(self):
        defaults = {
            'title':'',
            'tags':[],
            'file':None,
            }
        if self.show_sendalert:
            defaults['sendalert'] = True
        if self.workflow is not None:
            defaults['security_state'] = self.workflow.initial_state
        return defaults

    def form_fields(self):
        fields = []
        fields.append(('title', title_field))
        fields.append(('tags', tags_field))
        fields.append(('file', file_field))
        if self.show_sendalert:
            fields.append(('sendalert', sendalert_field))
        security_states = self._get_security_states()
        if security_states:
            fields.append(('security_state', security_field))
        return fields

    def form_widgets(self, fields):
        widgets = {
            'title':formish.Input(empty=''),
            'tags':karlwidgets.TagsAddWidget(),
            # single=True is irrelevant here, as we have nothing to delete
            'file':karlwidgets.FileUpload2(filestore = self.filestore, single=True),
            }
        security_states = self._get_security_states()
        schema = dict(fields)
        if 'sendalert' in schema:
            widgets['sendalert'] = karlwidgets.SendAlertCheckbox()
        if 'security_state' in schema:
            security_states = self._get_security_states()
            widgets['security_state'] = formish.RadioChoice(
                options=[ (s['name'], s['title']) for s in security_states],
                none_option=None)
        return widgets

    def __call__(self):
        api = TemplateAPI(self.context, self.request, 'Add File')
        layout_provider = get_layout_provider(self.context, self.request)
        if layout_provider is None:
            layout = api.community_layout
        else:
            layout = layout_provider('community')
        return {'api':api,
                'actions':(),
                'layout':layout}

    def handle_cancel(self):
        return HTTPFound(location=model_url(self.context, self.request))

    def handle_submit(self, converted):
        request = self.request
        context = self.context
        workflow = self.workflow

        creator = authenticated_userid(request)

        f = converted['file']

        if not f.file:
            raise ValidationError(file='Must upload a file')

        file = create_content(ICommunityFile,
                              title=converted['title'],
                              stream=f.file,
                              mimetype=get_upload_mimetype(f),
                              filename=f.filename,
                              creator=creator,
                              )
        self.check_upload_size(context, file, 'file')

        # For file objects, OSI's policy is to store the upload file's
        # filename as the objectid, instead of basing __name__ on the
        # title field).
        filename = basename_of_filepath(f.filename)
        file.filename = filename
        name = make_name(context, filename, raise_error=False)
        if not name:
            msg = 'The filename must not be empty'
            raise ValidationError(file=msg)
        # Is there a key in context with that filename?
        if name in context:
            msg = 'Filename %s already exists in this folder' % filename
            raise ValidationError(file=msg)
        context[name] = file

        if workflow is not None:
            workflow.initialize(file)
            if 'security_state' in converted:
                workflow.transition_to_state(file, request,
                                             converted['security_state'])

        # Tags, attachments, alerts
        set_tags(file, request, converted['tags'])
        if converted.get('sendalert'):
            alerts = queryUtility(IAlerts, default=Alerts())
            alerts.emit(file, request)

        self.filestore.clear()
        location = model_url(file, request)
        return HTTPFound(location=location)

def show_file_view(context, request):

    page_title = context.title
    api = TemplateAPI(context, request, page_title)

    client_json_data = dict(
        tagbox = get_tags_client_data(context, request),
        )

    actions = []
    if has_permission('create', context, request):
        actions.append(
            ('Edit', 'edit.html'),
            )
        actions.append(
            ('Delete', 'delete.html'),
            )

    # If we are in an attachments folder, the backto skips the
    # attachments folder and goes up to the grandparent
    from karl.models.interfaces import IAttachmentsFolder
    from repoze.bfg.traversal import find_interface
    attachments = find_interface(context, IAttachmentsFolder)
    if attachments is not None:
        up_to = context.__parent__.__parent__
    else:
        up_to = context.__parent__
    backto = {
        'href': model_url(up_to, request),
        'title': up_to.title,
        }

    fileinfo = getMultiAdapter((context, request), IFileInfo)
    previous, next = get_previous_next(context, request)

    # Get a layout
    community = find_community(context)
    layout_provider = get_layout_provider(context, request)
    if community is not None:
        layout = layout_provider('community')
    else:
        layout = layout_provider('generic')

    return render_template_to_response(
        'templates/show_file.pt',
        api=api,
        actions=actions,
        fileinfo=fileinfo,
        head_data=convert_to_script(client_json_data),
        backto=backto,
        previous_entry=previous,
        next_entry=next,
        layout=layout,
        )

def download_file_view(context, request):
    # To view image-ish files in-line, use thumbnail_view.
    f = context.blobfile.open()
    headers = [
        ('Content-Type', context.mimetype),
        ('Content-Length', str(context.size)),
    ]

    if 'save' in request.params:
        fname = context.filename
        if isinstance(fname, unicode):
            fname = fname.encode('utf-8')
        fname = fname.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        headers.append(
            ('Content-Disposition', 'attachment; filename=%s' % fname)
        )

    response = Response(headerlist=headers, app_iter=f)
    return response

def thumbnail_view(context, request):
    assert IImage.providedBy(context), "Context must be an image."
    filename = request.subpath[0] # <width>x<length>.jpg
    size = map(int, filename[:-4].split('x'))
    thumb = context.thumbnail(tuple(size))

    # XXX Allow browser caching be setting Last-modified and Expires
    #     and respecting If-Modified-Since requests with 302 responses.
    data = thumb.blobfile.open().read()
    return Response(body=data, content_type=thumb.mimetype)

class EditFolderFormController(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.workflow = get_workflow(ICommunityFolder, 'security', context)

    def _get_security_states(self):
        return get_security_states(self.workflow, self.context, self.request)

    def form_defaults(self):
        defaults = {
            'title':self.context.title,
            'tags':[],
            }

        if self.workflow is not None:
            defaults['security_state'] = self.workflow.state_of(self.context)
        return defaults

    def form_fields(self):
        fields = []
        fields.append(('title', title_field))
        fields.append(('tags', tags_field))
        security_states = self._get_security_states()
        if security_states:
            fields.append(('security_state', security_field))
        return fields

    def form_widgets(self, fields):
        tagdata = get_tags_client_data(self.context, self.request)
        widgets = {
            'title':formish.Input(empty=''),
            'tags':karlwidgets.TagsEditWidget(tagdata=tagdata),
            }
        security_states = self._get_security_states()
        schema = dict(fields)
        if 'security_state' in schema:
            security_states = self._get_security_states()
            widgets['security_state'] = formish.RadioChoice(
                options=[ (s['name'], s['title']) for s in security_states],
                none_option=None)
        return widgets

    def __call__(self):
        page_title = 'Edit %s' % self.context.title
        api = TemplateAPI(self.context, self.request, page_title)
        layout_provider = get_layout_provider(self.context, self.request)
        if layout_provider is None:
            layout = api.community_layout
        else:
            layout = layout_provider('community')
        return {'api':api,
                'actions':(),
                'layout':layout}

    def handle_cancel(self):
        return HTTPFound(location=model_url(self.context, self.request))

    def handle_submit(self, converted):
        context = self.context
        request = self.request
        workflow = self.workflow

        # *will be* modified event
        objectEventNotify(ObjectWillBeModifiedEvent(context))
        if workflow is not None:
            if 'security_state' in converted:
                workflow.transition_to_state(context, request,
                                             converted['security_state'])

        context.title = converted['title']

        # Tags, attachments, alerts
        set_tags(context, request, converted['tags'])

        # modified
        context.modified_by = authenticated_userid(request)
        objectEventNotify(ObjectModifiedEvent(context))

        location = model_url(context, request, query=
                             {'status_message':'Folder changed'})
        return HTTPFound(location=location)

class EditFileFormController(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.workflow = get_workflow(ICommunityFile, 'security', context)
        self.filestore = get_filestore(context, request, 'edit-file')

    def _get_security_states(self):
        return get_security_states(self.workflow, self.context, self.request)

    def form_defaults(self):
        context = self.context
        defaults = {
            'title':context.title,
            'tags':[], # initial values supplied by widget
            'file':SchemaFile(None, context.filename, context.mimetype),
            }
        if self.workflow is not None:
            defaults['security_state'] = self.workflow.state_of(context)
        return defaults

    def form_fields(self):
        fields = []
        fields.append(('title', title_field))
        fields.append(('tags', tags_field))
        fields.append(('file', file_field))
        security_states = self._get_security_states()
        if security_states:
            fields.append(('security_state', security_field))
        return fields

    def form_widgets(self, fields):
        tagdata = get_tags_client_data(self.context, self.request)
        widgets = {
            'title':formish.Input(empty=''),
            'tags':karlwidgets.TagsEditWidget(tagdata=tagdata),
            # single=True obligatory here, since we are out of sequence
            'file':karlwidgets.FileUpload2(filestore = self.filestore, single=True),
            }
        security_states = self._get_security_states()
        schema = dict(fields)
        if 'security_state' in schema:
            security_states = self._get_security_states()
            widgets['security_state'] = formish.RadioChoice(
                options=[ (s['name'], s['title']) for s in security_states],
                none_option=None)
        return widgets

    def __call__(self):
        page_title = 'Edit %s' % self.context.title
        api = TemplateAPI(self.context, self.request, page_title)
        layout_provider = get_layout_provider(self.context, self.request)
        if layout_provider is None:
            layout = api.community_layout
        else:
            layout = layout_provider('community')
        return {'api':api,
                'actions':(),
                'layout':layout}

    def handle_cancel(self):
        return HTTPFound(location=model_url(self.context, self.request))

    def handle_submit(self, converted):
        context = self.context
        request = self.request
        workflow = self.workflow

        # *will be* modified event
        objectEventNotify(ObjectWillBeModifiedEvent(context))
        if workflow is not None:
            if 'security_state' in converted:
                workflow.transition_to_state(context, request,
                                             converted['security_state'])

        context.title = converted['title']

        f = converted['file']

        if f.filename:
            context.upload(f.file)
            context.mimetype = get_upload_mimetype(f)
            context.filename = f.filename
            check_upload_size(context, context, 'file')
        else:
            meta = f.metadata
            if meta.get('remove'):
                raise ValidationError(file='Must supply a file')

        # Tags, attachments, alerts
        set_tags(context, request, converted['tags'])

        # modified
        context.modified_by = authenticated_userid(request)
        objectEventNotify(ObjectModifiedEvent(context))

        self.filestore.clear()
        location = model_url(context, request,
                             query={'status_message':'File changed'})
        return HTTPFound(location=location)


grid_folder_columns = [
    {"id": "sel", "label": '', "width": 32},
    {"id": "mimetype", "label": "Type", "width": 64},
    {"id": "title", "label": "Title", "width": 666 - (32 + 128 + 64)},
    {"id": "modified_date", "label": "Last Modified", "width": 128},
]

def jquery_grid_folder_view(context, request):

    start = request.params.get('start', '0')
    limit = request.params.get('limit', '10')
    sort_on = request.params.get('sortColumn', 'modified_date')
    reverse = request.params.get('sortDirection') == 'desc'

    payload = get_filegrid_client_data(context, request,
        start = int(start),
        limit = int(limit),
        sort_on = sort_on,
        reverse = reverse,
        )

    result = JSONEncoder().encode(payload)
    return Response(result, content_type="application/x-json")


def get_filegrid_client_data(context, request, start, limit, sort_on, reverse):
    """
    Gets the client data for the file grid.

    When used, the data needs to be injected to the templates::

        head_data=convert_to_script(dict(
            filegrid = get_filegrid_client_data(context, request,
                        start = 0,
                        limit = 10,
                        sort_on = 'modified_date',
                        reverse = False,
                        ),
            tags_field = get_tags_client_data(context, request),
            # ... data for more widgets
            # ...
            ))

    Or, returned to client in case of an ajax request.
    """

    api = TemplateAPI(context, request, 'any_title')

    ##columns = request.params.get('columns', '').capitalize() == 'True'

    # Now get the data that goes with this, then adapt into FileInfo
    info = get_container_batch(context, request,
        batch_start=start,
        batch_size=limit,
        sort_index=sort_on,
        reverse=reverse,
        )
    entries = [getMultiAdapter((item, request), IFileInfo)
        for item in info['entries']]

    records = []
    for entry in entries:
        records.append([
            entry.name,       # MUST hold the file name (id) for the select column.
            '<img src="%s/images/%s" alt="icon" title="%s"/>' % (
                api.static_url,
                entry.mimeinfo['small_icon_name'],
                entry.mimeinfo['title'],
                ),
            '%s<a href="%s" style="display: none;"/>' % (
                entry.title,
                entry.url,
                ),
            entry.modified,
            ])

    # We also send, in each case, the list of possible target folders.
    # They are needed for the grid reorganize (Move To) feature.
    # Since we need this when the grid content is loaded (or each time
    # it is reloaded), it is an obvious choice to factorize this information
    # together with the container batch, each time.
    #
    # The client expects a list of folder paths here, starting with a /,
    # such as:
    #      /
    #      /folder1
    #      /folder1/folderA
    #      ... etc ...
    #
    # The current folder should also be in the list.
    
    target_folders = get_target_folders(context)
    current_folder = get_current_folder(context)

    payload = dict(
        columns = grid_folder_columns,
        records = records,
        totalRecords = info['total'],
        sortColumn = sort_on,
        sortDirection = reverse and 'desc' or 'asc',
        targetFolders = target_folders,
        currentFolder = current_folder,
    )

    return payload

# --
# Reorganize (Delete and Move To)
# --

class ErrorResponse(Exception):
    
    def __init__(self, txt, **kw):
        self.__dict__.update(kw)
        super(ErrorResponse, self).__init__(txt)


def ajax_file_reorganize_delete_view(context, request):

    try:
        params = request.params
        filenames = params.getall('file[]')
        deleted = 0
        for filename in filenames:
            if filename not in context:
                # already deleted, ignore
                pass
            else:
                try:
                    del context[filename]
                except Exception, exc:
                    msg = str(exc) 
                    raise ErrorResponse(msg, filename=filename)
                else:
                    deleted += 1
        payload = dict(
            result = 'OK',
            deleted = deleted,
        )
    except ErrorResponse, exc:
        # this error will be sent back and its text displayed on the client.
        payload = dict(
            result = 'ERROR',
            error = str(exc),
            filename = exc.filename,
        )
        log.error('ajax_file_reorganize_delete_view error at filename="%s": %s' % 
            (exc.filename, str(exc)))
        transaction.doom()
    finally:
        pass

    result = JSONEncoder().encode(payload)
    # fake text/xml response type is needed for IE.
    return Response(result, content_type="text/html")


# XXX this should probably get moved to utils

def traverse_file_folder(context, folder):
    # Return the context folder specified in the "folder" parameter
    # "folder" contains an absolute path to the target, relative
    # to the community.
    community = find_community(context)
    assert folder.startswith('/')
    assert folder == '/' or not folder.endswith('/')
    c = community['files']
    if folder != '/':
        for segment in folder.split('/')[1:]:
            c = c[segment]
    return c
        
def get_target_folders(context):
    # Return the target folders for this community.
    #
    # The client expects a list of folder paths here, starting with a /,
    # such as:
    #      /
    #      /folder1
    #      /folder1/folderA
    #      ... etc ...
    #
    # The current folder should also be in the list.
    #
    community = find_community(context)
    catalog = find_catalog(context)
    root_path = model_path(community['files'])

    query = ICatalogSearch(context)
    total, docids, resolver = query(
        path = root_path, 
        interfaces = (ICommunityFolder, ),
        )
    target_paths = [catalog.document_map.address_for_docid(docid) for docid in docids]
    # sorting is important for the client visualization
    target_paths.sort()
    # always insert the root folder that was not returned by this search 
    target_paths.insert(0, root_path)

    # Process all the results
    target_folders = []
    for path in target_paths:
        # Now, only take the part after the community/files, ie, the path segments
        # after the root folder.
        assert path.startswith(root_path)
        # Just take the part after community/files
        target_folder = path[len(root_path):]
        # Correct the root folder from '' to '/'
        if not target_folder:
            target_folder = '/'
        target_folders.append(target_folder)

    return target_folders

def get_current_folder(context):
    # Calculate the current folder in the same format as the results
    # from get_target_folders (relative to community)
    community = find_community(context)
    root_path = model_path(community['files'])

    context_path = model_path(context)
    assert context_path.startswith(root_path)
    current_folder = context_path[len(root_path):]

    # Correct the root folder from '' to '/'
    if not current_folder:
        current_folder = '/'

    return current_folder

def ajax_file_reorganize_moveto_view(context, request):

    try:
        params = request.params
        filenames = params.getall('file[]')
        target_folder = params.get('target_folder', None)
        if target_folder is None:
            msg = 'Wrong parameters, `target_folder` is mandatory' 
            raise ErrorResponse(msg, filename="*")

        # find the target folder
        try:
            target_context = traverse_file_folder(context, target_folder)
        except KeyError:
            msg = 'Cannot find target folder "%s"' % (target_folder, )
            raise ErrorResponse(msg, filename="*")
        target_folder_url = model_url(target_context, request)

        moved = 0
        for filename in filenames:
            try:
                fileobj = context[filename]
                if fileobj == target_context:
                    msg = 'Cannot move a folder into itself'
                    raise ErrorResponse(msg, filename=filename)
                del context[filename]
                # We make sure there is a unique name in the new folder
                target_filename = make_unique_name(target_context, filename)
                target_context[target_filename] = fileobj
            except KeyError:
                msg = 'Cannot move to target folder <a href="%s">%s</a>' % (target_folder_url, target_folder)
                raise ErrorResponse(msg, filename=filename)
            moved += 1

        payload = dict(
            result = 'OK',
            moved = moved,
            targetFolder = target_folder,
            targetFolderUrl = target_folder_url,
        )
    except ErrorResponse, exc:
        # this error will be sent back and its text displayed on the client.
        payload = dict(
            result = 'ERROR',
            error = str(exc),
            filename = exc.filename,
        )
        log.error('ajax_file_reorganize_moveto_view error at filename="%s": %s' % 
            (exc.filename, str(exc)))
        transaction.doom()
    finally:
        pass

    result = JSONEncoder().encode(payload)
    # fake text/xml response type is needed for IE.
    return Response(result, content_type="text/html")


# --
# Multi Upload
# --

def make_temp_id(client_id):
    """Generate a unique tempdir id from the guaranteed unique client id"""
    temp_id = 'PLUPLOAD-' + client_id
    return temp_id

def ajax_file_upload_view(context, request):

    filename = "<>"
    try:
        params = request.params

        f = params.get('file', None)
        client_id = params.get('client_id', None)
        if f is None or client_id is None:
            msg = 'Wrong parameters, `file` is mandatory' 
            raise ErrorResponse(msg, client_id='')

        # XXX Handling of chunk uploads.
        # Even if we do not want chunks, we need to support it. :(
        #
        # The chunks can be disabled from the client by _not_ setting chunk_size.
        # However some uploader runtimes (most notably Flash, which is the main
        # target of the development because it does work on IE), either break with
        # error if chunking is disabled, or they ignore the chunk_size parameter
        # and use the chunking size they decide, nevertheless.
        chunks = int(params.get('chunks', '1'))
        chunk = int(params.get('chunk', '0'))

        is_first_chunk = chunk == 0
        is_last_chunk = chunk >= chunks - 1

        # (we allow chunks==0 chunk==0 as this happens with 0-length files)
        if chunk < 0 or chunks > 0 and chunk >= chunks:
            msg = 'Chunking inconsistence, `chunk` out of range' 
            raise ErrorResponse(msg, client_id='')

        end_batch = params.get('end_batch', None)

        filename = basename_of_filepath(f.filename)
        creator = authenticated_userid(request)
        tempfolder = find_tempfolder(context)
        # XXX We need to use the unique id from the client, as there is no way
        # to pass back the id we generate to the second chunk
        # (the flash runtime does not support this)
        temp_id = make_temp_id(client_id) 

        if is_first_chunk:
            # First chunk. Create the content object.

            fileobj = create_content(ICommunityFile,
                                  title=filename,   # XXX use filename as title, for now
                                  stream=f.file,
                                  mimetype=get_upload_mimetype(f),
                                  filename=filename,
                                  creator=creator,
                                  )

            # For file objects, OSI's policy is to store the upload file's
            # filename as the objectid, instead of basing __name__ on the
            # title field).
            fileobj.filename = filename

            # Store the image in the temp folder.
            fileobj.modified = datetime.datetime.now()
            tempfolder[temp_id] = fileobj

            # Add metadata to the newly created object
            # This also has a role in security: 
            # We store the original parent and creator.
            # If the transaction is finalized on a different parent, or creator,
            # we will doom it.
            fileobj.__transaction_parent__ = context
            fileobj.__client_file_id__ = client_id
            # Store the chunk info too
            fileobj.__chunks__ = chunks
            fileobj.__chunk__ = 0

        else:
            # Followup chunks (`chunk` > 0)

            fileobj = tempfolder[temp_id]

            # chunk security protection
            # to avoid attacks or malformed client_id parameters
            if fileobj.__client_file_id__ != client_id:
                msg = 'Inconsistent client file id'
                raise ErrorResponse(msg, client_id='')
            if fileobj.__transaction_parent__ != context:
                msg = 'Inconsistent batch transaction'
                raise ErrorResponse(msg, client_id=client_id)
            if fileobj.creator != creator:
                msg = 'Inconsistent ownership'
                raise ErrorResponse(msg, client_id=client_id)

            # chunk consistency check
            fileobj.__chunk__ += 1
            if fileobj.__chunk__ != chunk:
                msg = 'Chunking inconsistence, wrong chunk order'
                raise ErrorResponse(msg, client_id=client_id)

            # Append the file to the existing file
            bufsize = 8192
            blobf = fileobj.blobfile.open('a')
            while True:
                buf = f.file.read(bufsize)
                if not buf:
                    break
                blobf.write(buf)
            # Need to set the size
            fileobj.size = blobf.tell()
            # Close the file
            blobf.close()

        payload = dict(
            result = 'OK',
            filename = filename,
        )

        if is_last_chunk and end_batch is not None:
            # The client marks this as the last file in the batch.
            # We finalize the transaction by moving all files to the folder.
            end_batch = JSONDecoder().decode(end_batch)
            last_fileobj = fileobj
            # append the last file to the process queue
            end_batch.append(client_id)

            # Iterate on all the files in the just finishing batch.
            for client_id in end_batch:
                temp_id = make_temp_id(client_id) 
                fileobj = tempfolder[temp_id]

                # batch security protection
                # to avoid attacks or malformed end_batch parameters
                if fileobj.__client_file_id__ != client_id:
                    msg = 'Inconsistent client file id'
                    raise ErrorResponse(msg, client_id='')
                if fileobj.__transaction_parent__ != context:
                    msg = 'Inconsistent batch transaction'
                    raise ErrorResponse(msg, client_id=client_id)
                if fileobj.creator != last_fileobj.creator:
                    msg = 'Inconsistent ownership'
                    raise ErrorResponse(msg, client_id=client_id)

                # we are final, so remove all metadata
                del fileobj.__transaction_parent__
                del fileobj.__client_file_id__
                del fileobj.__chunks__
                del fileobj.__chunk__

                check_upload_size(context, fileobj, 'file')

                filename = fileobj.filename

                # XXX create a unique name, now
                name = make_unique_name(context, filename)
                if not name:
                    msg = 'The filename must not be empty'
                    raise ErrorResponse(msg, client_id=client_id)
                # Is there a key in context with that filename?

                # XXX Should we override the file, or raise an error,
                # XXX instead of just always creating the file with a unique name?
                #if name in context:
                #    msg = 'Filename %s already exists in this folder' % filename
                #   raise ErrorResponse(msg, client_id=client_id)

                del tempfolder[temp_id]
                context[name] = fileobj

                # XXX What to do with the workflow?
                workflow = get_workflow(ICommunityFolder, 'security', context)
                if workflow is not None:
                    workflow.initialize(fileobj)
                    #if 'security_state' in XXXconverted:
                    #    workflow.transition_to_state(fileobj, request,
                    #                                params['security_state'])

                # Tags, attachments
                #set_tags(fileobj, request, paramsXXX['tags'])

                # Alerts
                #if params.get('sendalert'):
                #    alerts = queryUtility(IAlerts, default=Alerts())
                #    alerts.emit(fileobj, request)

            payload['batch_completed'] = True;

    except ErrorResponse, exc:
        # this error will be sent back and its text displayed on the client.
        payload = dict(
            error = str(exc),
            client_id = exc.client_id,
        )
        log.error('ajax_file_upload_view at client_id="%s", filename="%s": %s' % 
            (client_id, filename, str(exc)))
        transaction.doom()
    finally:
        tempfolder = find_tempfolder(context)
        tempfolder.cleanup()

    result = JSONEncoder().encode(payload)
    # fake text/xml response type is needed for IE.
    return Response(result, content_type="text/html")
