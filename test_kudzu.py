
import logging
import re
import time

try:
    import threading
except ImportError:
    import dummy_threading as threading

import pytest
from werkzeug.test import EnvironBuilder, run_wsgi_app
from werkzeug.wrappers import BaseResponse

from kudzu import LoggingMiddleware, RequestContext, \
        RequestContextMiddleware, augment_handler, augment_logger


class HandlerMock(logging.Handler):
    """Logging handler which saves all logged records."""

    def __init__(self):
        super(HandlerMock, self).__init__()
        self.records = []
        self.messages = []

    def emit(self, record):
        self.records.append(record)
        self.messages.append(self.format(record))


def simple_app(environ, start_response):
    """Simple WSGI application"""
    data = 'Hello world!\n'
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-length', '%s' % len(data))]
    start_response('200 OK', response_headers)
    return [data]


def error_app(environ, start_response):
    """Simple WSGI application which always raises error."""
    raise ZeroDivisionError


def run_app(app, *args, **kwargs):
    """Executes WSGI application and returns response instance."""
    environ = EnvironBuilder(*args, **kwargs).get_environ()
    response = run_wsgi_app(app, environ)
    return BaseResponse(*response)


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
        builder = EnvironBuilder(headers={'USER_AGENT': 'testbot'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == 'testbot'

    def test_unknown_user_agent(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == '-'

    def test_referer(self):
        builder = EnvironBuilder(headers={'REFERER': 'http://localhost'})
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
        pattern = r'\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}'
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


class TestRequestContextMiddleware(object):
    """Tests `RequestContextMiddleware` class."""

    def test_context_is_none_after_request(self):
        app = RequestContextMiddleware(simple_app)
        assert RequestContext.get() is None
        response = run_app(app, '/')
        assert response.status_code == 200
        assert RequestContext.get() is None

    def test_context_is_none_after_error(self):
        app = RequestContextMiddleware(error_app)
        with pytest.raises(ZeroDivisionError):
            run_app(app, '/')
        assert RequestContext.get() is None

    def test_context_is_set_during_request(self):
        @RequestContextMiddleware
        def app(environ, start_response):
            context = RequestContext.get()
            assert environ['kudzu.context'] is context
            assert context.log_vars['uri'] == '/'
            return simple_app(environ, start_response)
        response = run_app(app, '/')
        assert response.status_code == 200

    def test_duplicate_request_context_raises(self):
        app = RequestContextMiddleware(RequestContextMiddleware(simple_app))
        with pytest.raises(RuntimeError):
            run_app(app, '/')


class TestLoggingMiddleware(object):
    """Tests `LoggingMiddleware` class."""

    def setup_method(self, method):
        self.handler = HandlerMock()
        self.logger = logging.getLogger('test_kudzu')
        self.logger.addHandler(self.handler)
        self.logger.level = logging.DEBUG

    def teardown_method(self, method):
        self.logger.removeHandler(self.handler)

    def wrap_app(self, app):
        rv = LoggingMiddleware(app, self.logger)
        # Fake response time in log messages
        rv.response_format = rv.response_format.replace('%(msecs)s', '7')
        rv.exception_format = rv.exception_format.replace('%(msecs)s', '7')
        return RequestContextMiddleware(rv)

    def test_middleware_is_created_with_detail_logger(self):
        mw = LoggingMiddleware(simple_app)
        assert mw.logger.name == 'wsgi'

    def test_middleware_is_created_with_logger_name(self):
        mw = LoggingMiddleware(simple_app, self.logger.name)
        assert mw.logger is self.logger

    def test_middleware_is_created_with_logger_instance(self):
        mw = LoggingMiddleware(simple_app, self.logger)
        assert mw.logger is self.logger

    def test_request_and_response_are_logged(self):
        app = self.wrap_app(simple_app)
        response = run_app(app)
        assert response.status_code == 200
        assert len(self.handler.records) == 2
        assert self.handler.records[0].msg == \
            'Request "GET HTTP/1.1 /" from -, user agent "-", referer -'
        assert self.handler.records[1].msg == \
            'Response status 200 in 7 ms, size 13 bytes'

    def test_exception_is_logged(self):
        app = self.wrap_app(error_app)
        with pytest.raises(ZeroDivisionError):
            run_app(app)
        assert self.handler.records[0].msg == \
            'Request "GET HTTP/1.1 /" from -, user agent "-", referer -'
        assert self.handler.records[1].msg == 'Exception in 7 ms.'
        assert self.handler.records[1].exc_info is not None

    def test_missing_request_context_raises(self):
        app = LoggingMiddleware(simple_app, self.logger)
        with pytest.raises(RuntimeError):
            run_app(app)


class TestRequestContextFilter(object):

    format = '["%(method)s %(proto)s %(uri)s" from %(addr)s] %(message)s'

    def setup_method(self, method):
        self.handler = HandlerMock()
        self.logger = logging.getLogger('test_kudzu')
        self.logger.addHandler(self.handler)

    def teardown_method(self, method):
        self.logger.removeHandler(self.handler)

    def test_augment_handler(self):
        augment_handler(self.handler, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_augment_logger(self):
        augment_logger(self.logger, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_augment_logger_by_name(self):
        augment_logger(self.logger.name, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_log_wo_context(self):
        augment_logger(self.logger, format=self.format)
        self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == '["- - -" from -] Hello Kudzu'

    def test_log_w_context(self):
        augment_logger(self.logger, format=self.format)
        builder = EnvironBuilder(path='/foo',
                                 environ_base={'REMOTE_ADDR': '127.0.0.1'})
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /foo" from 127.0.0.1] Hello Kudzu'
