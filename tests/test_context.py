
from __future__ import absolute_import

import re
import time

try:
    import threading
except ImportError:
    import dummy_threading as threading

import pytest
from werkzeug.test import EnvironBuilder

from kudzu import get_remote_addr, get_request_id, RequestContext


class TestRequestContext(object):
    """Tests `RequestContext` class."""

    def test_request_uri_wo_query(self):
        builder = EnvironBuilder(base_url='http://example.com/foo',
                                 path='/bar')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uri'] == '/foo/bar'

    def test_request_uri_w_query(self):
        builder = EnvironBuilder(base_url='http://example.com/foo',
                                 path='/bar?baz=1')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uri'] == '/foo/bar?baz=1'

    def test_method(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['method'] == 'GET'

    def test_remote_user(self):
        builder = EnvironBuilder(environ_base={'REMOTE_USER': 'john.doe'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['user'] == 'john.doe'

    def test_unknown_remote_user(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['user'] == '-'

    def test_remote_addr(self):
        builder = EnvironBuilder(environ_base={'REMOTE_ADDR': '127.0.0.1'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['addr'] == '127.0.0.1'

    def test_unknown_remote_addr(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['addr'] == '-'

    def test_host(self):
        builder = EnvironBuilder(base_url='http://example.com/foo')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['host'] == 'example.com'

    def test_proto(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['proto'] == 'HTTP/1.1'

    def test_user_agent(self):
        builder = EnvironBuilder(headers={'User-Agent': 'testbot'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == 'testbot'

    def test_unknown_user_agent(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == '-'

    def test_referer(self):
        builder = EnvironBuilder(headers={'Referer': 'http://localhost'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['referer'] == 'http://localhost'

    def test_unknown_referer(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['referer'] == '-'

    def test_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_status('200 OK')
        assert context.log_vars['status'] == '200'

    def test_invalid_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_status('XXX NOT OK')
        assert context.log_vars['status'] == '???'

    def test_uknown_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        # Before start_response was called
        assert context.log_vars['status'] == '-'

    def test_micros(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert 0 <= int(context.log_vars['micros']) < 5000

    def test_msecs(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert 0 <= int(context.log_vars['msecs']) < 5

    def test_time(self):
        builder = EnvironBuilder()
        min_time = time.time()
        context = RequestContext(builder.get_environ())
        max_time = time.time()
        assert int(min_time) <= int(context.log_vars['time']) <= int(max_time)

    def test_ctime(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        pattern = r'^\w{3} \w{3} [\d ]\d \d{2}:\d{2}:\d{2} \d{4}$'
        assert re.match(pattern, context.log_vars['ctime'])

    def test_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_response_size('42')
        assert context.log_vars['rsize'] == '42'

    def test_invalid_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_response_size('XXX')
        assert context.log_vars['rsize'] == '???'

    def test_unknown_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        # No Content-Length header
        assert context.log_vars['rsize'] == '-'

    def test_request_id(self):
        builder = EnvironBuilder(headers={'X-Request-ID': 'xyz'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['rid'] == 'xyz'


class TestRequestContextStack(object):
    """Tests access to thread local `RequestContext` instance."""

    def setup_method(self, method):
        RequestContext.reset()

    def teardown_method(self, method):
        RequestContext.reset()

    def test_push_pop_context(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert RequestContext.get() is None
        context.push()
        assert RequestContext.get() is context
        context.pop()
        assert RequestContext.get() is None

    def test_push_pop_multiple_contexts(self):
        builder = EnvironBuilder()
        context1 = RequestContext(builder.get_environ())
        context2 = RequestContext(builder.get_environ())
        context1.push()
        assert RequestContext.get() is context1
        context2.push()
        assert RequestContext.get() is context2
        context2.pop()
        assert RequestContext.get() is context1
        context1.pop()
        assert RequestContext.get() is None

    def test_push_pop_context_multiple_times(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.push()
        assert RequestContext.get() is context
        context.push()
        assert RequestContext.get() is context
        context.pop()
        assert RequestContext.get() is context
        context.pop()
        assert RequestContext.get() is None

    def test_pop_missing_context(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        with pytest.raises(RuntimeError):
            context.pop()
        assert RequestContext.get() is None

    def test_pop_wrong_context(self):
        builder = EnvironBuilder()
        context1 = RequestContext(builder.get_environ())
        context2 = RequestContext(builder.get_environ())
        context1.push()
        with pytest.raises(RuntimeError):
            context2.pop()
        assert RequestContext.get() is context1

    def test_threading(self):
        builder = EnvironBuilder()
        context1 = RequestContext(builder.get_environ())
        context2 = RequestContext(builder.get_environ())
        def target1():
            assert RequestContext.get() is None
            context1.push()
            assert RequestContext.get() is context1
            t2.start()
            t2.join()
            assert RequestContext.get() is context1
        def target2():
            assert RequestContext.get() is None
            context2.push()
            assert RequestContext.get() is context2
        t1 = threading.Thread(target=target1)
        t2 = threading.Thread(target=target2)
        assert RequestContext.get() is None
        t1.start()
        t1.join()
        assert RequestContext.get() is None


class TestContextGetters(object):

    def test_remote_addr_is_returned(self):
        builder = EnvironBuilder(environ_base={'REMOTE_ADDR': '127.0.0.1'})
        context = RequestContext(builder.get_environ())
        with context:
            assert get_remote_addr() == '127.0.0.1'

    def test_remote_addr_is_not_returned_wo_context(self):
        assert get_remote_addr() is None

    def test_remote_addr_is_not_returned_if_not_kwown(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        with context:
            assert get_remote_addr() is None

    def test_request_id_is_returned(self):
        builder = EnvironBuilder(headers={'X-Request-ID': 'xyz'})
        context = RequestContext(builder.get_environ())
        with context:
            assert get_request_id() == 'xyz'

    def test_request_id_is_not_returned_wo_context(self):
        assert get_request_id() is None

    def test_request_id_is_not_returned_if_not_kwown(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        with context:
            assert get_request_id() is None
