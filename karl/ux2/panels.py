from cgi import escape

from pyramid.encode import urlencode
from pyramid.security import authenticated_userid
from pyramid.security import has_permission
from pyramid.traversal import resource_path

from karl.content.views.utils import fetch_attachments
from karl.utilities.image import thumb_url
from karl.utilities.interfaces import IKarlDates
from karl.utils import find_intranets
from karl.utils import find_profiles
from karl.utils import find_community
from karl.utils import find_chatter
from karl.views.people import PROFILE_THUMB_SIZE
from karl.views.utils import get_user_home
from karl.views.utils import make_name


PROFILE_ICON_SIZE = (25, 25)
EMPTY_CONTEXT = {}


def generic_panel(context, request):
    return {}


def column_one(context, request):
    layout_manager = request.layout_manager
    layout = layout_manager.layout
    render = layout_manager.render_panel
    if layout.portlets:
        return '\n'.join(
            [render(name, *args, **kw)
             for name, args, kw in layout.portlets])
    return ''


def global_nav(context, request):

    def menu_item(title, url, id=None, count=None, secondary=None):
        if id is None:
            id = make_name(EMPTY_CONTEXT, title)
        selected = request.resource_url(context).startswith(url)
        if secondary is not None and not selected:
            selected = request.resource_url(context).startswith(secondary)
        item = dict(title=title,
                    url=url,
                    id=id,
                    selected=selected and 'selected' or None)
        if count is not None:
            item['count'] = count
        return item

    layout = request.layout_manager.layout
    site = layout.site
    menu_items = [
        menu_item("Communities", request.resource_url(site, 'communities')),
        menu_item("People", layout.people_url, secondary=layout.profiles_url),
        menu_item("Feeds", request.resource_url(site, 'contentfeeds.html')),
        ]
    intranets = find_intranets(site)
    if layout.current_intranet is not None:
        menu_items.insert(0, menu_item("Intranet",
             request.resource_url(intranets)))
    if layout.should_show_calendar_tab:
        menu_items.append(menu_item("Calendar",
             request.resource_url(site, 'offices', 'calendar')))
    chatter = find_chatter(site)
    menu_items.append(menu_item("Chatter", request.resource_url(chatter)))
    # XXX Radar is disabled for the time.
    ## menu_items.append(menu_item("Radar", "#", count="7"))
    overflow_menu = []
    if layout.user_is_staff:
        overflow_menu.append(menu_item("Tags",
             request.resource_url(site, 'tagcloud.html'), id='tagcloud'))
    return {'nav_menu': menu_items, 'overflow_menu': overflow_menu}


def context_tools(context, request, tools=None):
    overflow_menu = []
    community = find_community(context)
    if community:
        url = request.resource_url(community, 'tagcloud.html')
        selected = 'tagcloud.html' in request.path_url
        overflow_menu.append(dict(title="Tags",
                                  url=url,
                                  selected=selected,
                                  id='tagcloud'))
    return {'tools': tools, 'overflow_menu': overflow_menu}


def actions_menu(context, request, actions):
    if not actions:
        return '' # short circuit renderer

    # Allow views to pass in UX2 action menu.  The menu will be a dict.
    if isinstance(actions, dict):
        return actions

    # Backwards compatability layer.  Attempt to convert old style UX1 actions
    # into newer menu structure.
    converted = []
    addables = []
    overflow_menu = []
    for title, url in actions:
        if title.startswith('Add '):
            addables.append((title, url))
        # very difficult to convert a simple tuple structure into a full
        # featured ux2 menu. Let's add the overflow menu if there's a manage
        # option and put all remaining options after that there.
        elif title.startswith('Manage ') or overflow_menu != []:
            overflow_menu.append({'title': title, 'url': url})
        else:
            converted.append({'title': title, 'url': url})

    if len(addables) > 2:
        converted.insert(0, {
            'title': 'Add',
            'subactions': [{'title': title[4:], 'url': url}
                            for title, url in addables]})
    else:
        converted = [{'title': title, 'url': url}
                     for title, url in addables] + converted

    menu = {'actions': converted}

    if len(overflow_menu) > 0:
        menu['overflow_menu'] = overflow_menu

    return menu


def personal_tools(context, request):
    profiles = find_profiles(context)
    name = authenticated_userid(request)
    profile = profiles[name]
    photo = profile.get('photo')
    if photo is not None:
        icon_url = thumb_url(photo, request, PROFILE_ICON_SIZE)
    else:
        icon_url = request.static_url('karl.views:static/img/person.png')
    profile_url = request.resource_url(profile)
    logout_url = "%s/logout.html" % request.application_url
    return {'profile_name': profile.title,
            'profile_url': profile_url,
            'icon_url': icon_url,
            'logout_url': logout_url}


def status_message(context, request):
    message = request.params.get('status_message')
    if message:
        return '<div class="notification info">%s</div>' % escape(message)
    return ''


def error_message(context, request):
    message = request.layout_manager.layout.error_message
    if message:
        return '<div class="portalErrorMessage">%s</div>' % escape(message)
    return ''


def global_logo(context, request):
    home_context, home_path = get_user_home(context, request)
    return {'logo_title': request.registry.settings.get('system_name', 'KARL'),
            'logo_href': request.resource_url(home_context, *home_path)}

def my_communities(context, request, my_communities, preferred_communities):
    return {
        'my_communities': my_communities,
        'preferred_communities': preferred_communities}


def my_tags(context, request, tags):
    profiles = find_profiles(context)
    name = authenticated_userid(request)
    profile = profiles[name]
    return {'tags': tags,
            'firstname': profile.firstname,}


# --
# XXX This used to belong to "api". Now, we need it from the footer
# panel. In case the same info is needed from other panels, there
# is a choice to reuse this method from that panel, or, if generic
# enough, move it to "layout".

from pyramid.url import resource_url
from pyramid.traversal import quote_path_segment
from repoze.lemonade.content import get_content_type

from karl.models.interfaces import ICommunity


def intranets_info(context, request):
    """Get information for the footer and intranets listing"""
    intranets_info = []
    intranets = find_intranets(context)
    if intranets:
        intranets_url = resource_url(intranets, request)
        for name, entry in intranets.items():
            try:
                content_iface = get_content_type(entry)
            except ValueError:
                continue
            href = '%s%s/' % (intranets_url, quote_path_segment(name))
            if content_iface == ICommunity:
                intranets_info.append({
                        'title': entry.title,
                        'intranet_href': href,
                        'edit_href': href + '/edit_intranet.html',
                        })
        # Sort the list
        def intranet_sort(x, y):
            if x['title'] > y['title']:
                return 1
            else:
                return -1
        intranets_info.sort(intranet_sort)
    return intranets_info


def footer(context, request):
    return {
        'intranets_info': intranets_info(context, request),
        }


def skinswitcher(context, request):
    using_ux2 = request.cookies.get('ux2') == 'true'
    return {
        'skinswitcher': dict(value='false', label='LEGACY') \
            if using_ux2 \
            else dict(value='true', label='UX2'),
        }


def search(context, request):
    scope_options = []
    scope_options.append(dict(
        path = '',
        name = 'all KARL',
        label = 'all KARL',
        selected = True,
        ))
    # We add a second option, in case, context is inside a community.
    community = find_community(context)
    if community:
        # We are in a community!
        scope_options.append(dict(
            path = resource_path(community),
            name = 'this community',
            label = community.title,
        ))

    return {
        'scope_options': scope_options,
        }


def attachments(context, request, other_context=None):
    if other_context:
        context = other_context
    get_attachments = getattr(context, 'get_attachments', None)
    if not get_attachments:
        return ''
    folder = get_attachments()
    return {'attachments': fetch_attachments(folder, request)}


def comments(context, request):
    profiles = find_profiles(context)
    karldates = request.registry.getUtility(IKarlDates)
    comments = []
    for comment in context['comments'].values():
        profile = profiles.get(comment.creator)
        author_name = profile.title
        author_url = resource_url(profile, request)

        newc = {}
        newc['id'] = comment.__name__
        if has_permission('edit', comment, request):
            newc['edit_url'] = resource_url(comment, request, 'edit.html')
        else:
            newc['edit_url'] = None

        if has_permission('delete', comment, request):
            newc['delete_url'] = resource_url(comment, request, 'delete.html')
        else:
            newc['delete_url'] = None

        if has_permission('administer', comment, request):
            newc['advanced_url'] = resource_url(comment, request, 'advanced.html')
        else:
            newc['advanced_url'] = None

        # Display portrait
        photo = profile.get('photo')
        if photo is not None:
            photo_url = thumb_url(photo, request, PROFILE_THUMB_SIZE)
        else:
            photo_url = request.static_url(
                "karl.views:static/images/defaultUser.gif")
        newc["portrait_url"] = photo_url

        newc['author_url'] = author_url
        newc['author_name'] = author_name

        newc['date'] = karldates(comment.created, 'longform')
        newc['timestamp'] = comment.created
        newc['text'] = comment.text

        # Fetch the attachments info
        newc['attachments'] = fetch_attachments(comment, request)
        comments.append(newc)
    comments.sort(key=lambda c: c['timestamp'])
    return {'comments': comments}


def tagbox(context, request):
    return {}


def quip_search(context, request):
    return {}


def quip_tags(context, request, tag_list):
    return {'tag_list': tag_list}


def followers(context, request):
    return {}


def discover(context, request):
    return {}


def follow_info(context, request, creators):
    return {'creators': creators,
            'chatter_url': request.resource_url(context)}


def wiki_lock(context, request, lock_info):
    return {'lock_info': lock_info}


def searchresults(context, request, r, doc, result_display):
    return {'r': r, 'result_display': result_display, 'doc': doc}


def site_announcement(context, request):
    if "show_announcement" not in request.params:
        # We only want to show the site announcement in the sample
        # app if we ask for it. We'll make a link on the sample page
        # to make this obvious
        return {}
    announcement = """
    Praesent commodo cursus magna, vel scelerisque nisl
        consectetur et. Sed posuere consectetur est at lobortis.
        Aenean eu leo quam. Pellentesque ornare sem lacinia quam
        venenatis vestibulum."""
    return dict(
        ann_headline="The dismissible site announcement",
        ann_body=announcement,
        ann_href="/",
    )


def grid_header(context, request, letters=None, filters=None, formats=None,
                actions=None):
    return {
        'letters': letters,
        'filters': filters,
        'formats': formats,
        'actions': actions}


def grid_footer(context, request, batch):
    # Pagination
    batch_size = batch['batch_size']
    n_pages = (batch['total'] - 1) / batch_size + 1
    if n_pages <= 1:
        batch['pagination'] = False
        return batch

    url = request.path_url
    def page_url(page):
        params = request.GET.copy()
        params['batch_start'] = str(page * batch_size)
        return '%s?%s' % (url, urlencode(params))

    batch['pagination'] = True
    current = batch['batch_start'] / batch['batch_size']
    if current > 0:
        batch['prev_url'] = page_url(current - 1)
    else:
        batch['prev_url'] = None
    if current + 1 < n_pages:
        batch['next_url'] = page_url(current + 1)
    else:
        batch['next_url'] = None
    pages = []
    for i in xrange(n_pages):
        ellipsis = i != 0 and i != n_pages - 1 and abs(current - i) > 3
        if ellipsis:
            if pages[-1]['name'] != 'ellipsis':
                pages.append({
                    'name': 'ellipsis',
                    'title': '...',
                    'url': None,
                    'selected': False})
        else:
            title = '%d' % (i + 1)
            pages.append({
                'name': title,
                'title': title,
                'url': page_url(i),
                'selected': i == current})

    batch['pages'] = pages
    return batch


def extra_css(context, request):
    layout = request.layout_manager.layout
    static_url = request.static_url
    css = []
    for spec in layout.extra_css:
        # We allow spec to be an absolute url, in which case
        # we "just use it".
        if not (spec.startswith('http://') or spec.startswith('https://')):
            spec = static_url(spec)
        css.append('\t\t<link rel="stylesheet" href="%s" />' % spec)
    return '\n'.join(css)


def extra_js(context, request):
    layout = request.layout_manager.layout
    static_url = request.static_url
    js = []
    for spec in layout.extra_js:
        # We allow spec to be an absolute url, in which case
        # we "just use it".
        if not (spec.startswith('http://') or spec.startswith('https://')):
            spec = static_url(spec)
        # XXX We make it all defer. Revise and provide a parameter,
        # XXX if it makes sense!
        defer = True
        js.append('\t\t<script src="%s" %s></script>' % (spec, 'defer' if defer else ''))
    return '\n'.join(js)


def extra_css_head(context, request):
    layout = request.layout_manager.layout
    static_url = request.static_url
    css = []
    for spec in layout.extra_css_head:
        # We allow spec to be an absolute url, in which case
        # we "just use it".
        if not (spec.startswith('http://') or spec.startswith('https://')):
            spec = static_url(spec)
        css.append('\t\t<link rel="stylesheet" href="%s" />' % spec)
    return '\n'.join(css)


def extra_js_head(context, request):
    layout = request.layout_manager.layout
    static_url = request.static_url
    js = []
    for spec in layout.extra_js_head:
        # We allow spec to be an absolute url, in which case
        # we "just use it".
        if not (spec.startswith('http://') or spec.startswith('https://')):
            spec = static_url(spec)
        # XXX We make it all non-defer. Revise and provide a parameter,
        # XXX if it makes sense!
        defer = False
        js.append('\t\t<script src="%s" %s></script>' % (spec, 'defer' if defer else ''))
    return '\n'.join(js)


def extra_head(context, request):
    # FIXME: so what's the point of this, then?
    return ''


def related_tags(context, request, related):
    def tagurl(tag):
        return request.resource_url(context, 'showtag', tag)
    return {'related': related,
            'tagurl': tagurl}
