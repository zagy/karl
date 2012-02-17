import unittest

from pyramid import testing

from karl import testing as karltesting



class Test_recent_chatter(unittest.TestCase):

    def setUp(self):
        testing.cleanUp()

    def tearDown(self):
        testing.cleanUp()

    def _callFUT(self, context, request):
        from karl.views.chatter import recent_chatter
        return recent_chatter(context, request)

    def test_empty_chatterbox(self):
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox()
        request = testing.DummyRequest()
        info = self._callFUT(context, request)
        self.assertEqual(info['api'].page_title, 'Recent Chatter')
        self.assertEqual(list(info['recent']), [])
        self.failIf(context._tag or context._names or context._community)
        self.assertEqual(info['qurl'](context), 'http://example.com/chatter/')

    def test_filled_chatterbox(self):
        site = testing.DummyModel()
        quip1, quip2, quip3 = object(), object(), object()
        site['chatter'] = context = _makeChatterbox((quip3, quip2, quip1))
        request = testing.DummyRequest()
        info = self._callFUT(context, request)
        self.assertEqual(list(info['recent']), [quip3, quip2, quip1])

    def test_overfilled_chatterbox(self):
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox([object()] * 30)
        request = testing.DummyRequest()
        info = self._callFUT(context, request)
        self.assertEqual(len(list(info['recent'])), 20)


class Test_tag_chatter(unittest.TestCase):

    def setUp(self):
        testing.cleanUp()

    def tearDown(self):
        testing.cleanUp()

    def _callFUT(self, context, request):
        from karl.views.chatter import tag_chatter
        return tag_chatter(context, request)

    def test_wo_subpath(self):
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox()
        request = testing.DummyRequest()
        found = self._callFUT(context, request)
        self.assertEqual(found.location, 'http://example.com/chatter/')

    def test_empty_chatterbox(self):
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox()
        request = testing.DummyRequest(subpath=('sometag',))
        info = self._callFUT(context, request)
        self.assertEqual(info['api'].page_title, 'Chatter: #sometag')
        self.assertEqual(list(info['recent']), [])
        self.assertEqual(context._tag, 'sometag')
        self.failIf(context._names or context._community)
        self.assertEqual(info['qurl'](context), 'http://example.com/chatter/')

    def test_filled_chatterbox(self):
        site = testing.DummyModel()
        quip1, quip2, quip3 = object(), object(), object()
        site['chatter'] = context = _makeChatterbox((quip3, quip2, quip1))
        request = testing.DummyRequest(subpath=('sometag',))
        info = self._callFUT(context, request)
        self.assertEqual(list(info['recent']), [quip3, quip2, quip1])
        self.assertEqual(context._tag, 'sometag')
        self.failIf(context._names or context._community)

    def test_overfilled_chatterbox(self):
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox([object()] * 30)
        request = testing.DummyRequest(subpath=('sometag',))
        info = self._callFUT(context, request)
        self.assertEqual(len(list(info['recent'])), 20)
        self.assertEqual(context._tag, 'sometag')
        self.failIf(context._names or context._community)


class Test_add_chatter(unittest.TestCase):

    def setUp(self):
        testing.cleanUp()

    def tearDown(self):
        testing.cleanUp()

    def _callFUT(self, context, request):
        from karl.views.chatter import add_chatter
        return add_chatter(context, request)

    def test_it(self):
        _registerSecurityPolicy('user')
        site = testing.DummyModel()
        site['chatter'] = context = _makeChatterbox()
        request = testing.DummyRequest()
        request.POST['text'] = 'This is a quip.'
        found = self._callFUT(context, request)
        self.assertEqual(found.location, 'http://example.com/chatter/')
        self.assertEqual(context._added.text, 'This is a quip.')
        self.assertEqual(context._added.creator, 'user')


def _makeChatterbox(recent=()):

    class _Chatterbox(testing.DummyModel):
        _names = _tag = _community = _added = None
        def __init__(self, recent):
            self._recent = recent
        def addQuip(self, text, creator):
            self._added = testing.DummyModel(text=text, creator=creator)
        def recent(self):
            return self._recent
        def recentWithNames(self, *names):
            self._names = names
            return self._recent
        def recentWithTag(self, tag):
            self._tag = tag
            return self._recent
        def recentWithCommunity(self, community):
            self._community = community
            return self._recent

    return _Chatterbox(recent)


def _registerSecurityPolicy(userid):
    karltesting.registerDummySecurityPolicy(userid)


class DummySecurityPolicy:
    """ A standin for both an IAuthentication and IAuthorization policy """
    def __init__(self, userid=None, groupids=(), permissions=None):
        self.userid = userid

    def authenticated_userid(self, request):
        return self.userid
