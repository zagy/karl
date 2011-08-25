import datetime
import time

from webob.exc import HTTPFound
from repoze.bfg.security import authenticated_userid
from repoze.bfg.url import model_url
from karl.models.interfaces import IContainerVersion

from karl.models.subscribers import index_content
from karl.utilities.lock import lock_info_for_view
from karl.utils import find_catalog
from karl.utils import find_repo
from karl.utils import find_profiles
from karl.views.api import TemplateAPI
from karl.views.utils import make_unique_name


def show_history(context, request, tz=None):
    repo = find_repo(context)
    profiles = find_profiles(context)

    def display_record(record):
        editor = profiles[record.user]
        return {
            'date': format_local_date(record.archive_time, tz),
            'editor': {
                'name': editor.title,
                'url': model_url(editor, request),
                },
            'preview_url': model_url(
                context, request, 'preview.html',
                query={'version_num': str(record.version_num)}),
            'restore_url': model_url(
                context, request, 'revert',
                query={'version_num': str(record.version_num)}),
            'is_current': record.current_version == record.version_num,
        }

    try:
        history = repo.history(context.docid)
    except:
        history = []
    history = map(display_record, history)
    history.reverse()

    page_title = 'History for %s' % context.title

    backto = {
        'href': model_url(context, request),
        'title': context.title
    }

    return {
        'api': TemplateAPI(context, request, page_title),
        'history': history,
        'backto': backto,
        'lock_info': lock_info_for_view(context, request),
    }


def revert(context, request):
    repo = find_repo(context)
    version_num = int(request.params['version_num'])
    for version in repo.history(context.docid):
        if version.version_num == version_num:
            break
    else:
        raise ValueError('No such version: %d' % version_num)
    context.revert(version)
    repo.reverted(context.docid, version_num)
    catalog = find_catalog(context)
    catalog.reindex_doc(context.docid, context)
    return HTTPFound(location=model_url(context, request))


def show_trash(context, request, tz=None):
    repo = find_repo(context)
    profiles = find_profiles(context)

    def display_record(record):
        deleted_by = profiles[record.deleted_by]
        version = repo.history(record.docid, only_current=True)[0]
        return {
            'date': format_local_date(record.deleted_time, tz),
            'deleted_by': {
                'name': deleted_by.title,
                'url': model_url(deleted_by, request),
                },
            'restore_url': model_url(
                context, request, 'restore',
                query={'docid': str(record.docid), 'name': record.name}),
            'title': version.title,
        }

    try:
        contents = repo.container_contents(context.docid)
        deleted = contents.deleted
    except:
        deleted = []

    return {
        'api': TemplateAPI(context, request, 'Trash'),
        'deleted': map(display_record, deleted),
    }


def _undelete(repo, parent, docid, name):
    version = repo.history(docid, only_current=True)[0]
    doc = version.klass()
    doc.revert(version)

    try:
        container = repo.container_contents(docid)
    except:
        container = None

    if container is not None:
        for child_name, child_docid in container.map.items():
            _undelete(repo, doc, child_docid, child_name)

    if name in parent:
        # Choose a non-conflicting name to restore to.  (LP #821206)
        name = make_unique_name(parent, name)

    parent.add(name, doc, send_events=False)
    return doc


def undelete(context, request):
    repo = find_repo(context)
    docid = int(request.params['docid'])
    name = request.params['name']
    doc = _undelete(repo, context, docid, name)
    repo.archive_container(IContainerVersion(context),
                           authenticated_userid(request))
    index_content(context, None)
    return HTTPFound(location=model_url(doc, request))


epoch = datetime.datetime.utcfromtimestamp(0)


def format_local_date(date, tz=None, time_module=time):
    """Format a UTC datetime for the local time zone."""
    # time_module is a testing hook.
    if tz is None:
        if not time_module.daylight:
            # DST does not apply to the local time zone.
            tz = time_module.timezone
        else:
            # Figure out whether DST applied on the given date in the
            # local time zone.
            delta = date - epoch
            seconds = delta.days * 86400 + delta.seconds
            struct_time = time_module.localtime(seconds)
            if struct_time.tm_isdst:
                tz = time_module.altzone
            else:
                tz = time_module.timezone

    local = date - datetime.timedelta(seconds=tz)
    return local.strftime('%Y-%m-%d %H:%M')