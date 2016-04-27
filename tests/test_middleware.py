
from __future__ import absolute_import

import logging
import re

import pytest
from werkzeug.test import EnvironBuilder, run_wsgi_app
from werkzeug.wrappers import BaseResponse

from kudzu import kudzify_app, RequestContext, LoggingMiddleware, \
    RequestContextMiddleware, RequestIDMiddleware


class HandlerMock(logging.Handler):
    """Logging handler which saves all logged records."""

    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []
        self.messages = []

    def emit(self, record):
        self.records.append(record)


def simple_app(environ, start_response, extra_headers=None):
    """Simple WSGI application"""
    data = 'Hello world!\n'
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-length', '%s' % len(data))]
    if extra_headers:
        response_headers += extra_headers
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


class TestLoggingMiddleware(object):
    """Tests `LoggingMiddleware` class."""

    def setup_method(self, method):
        self.handler = HandlerMock()
        self.logger = logging.getLogger('test_middleware')
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
            'Request "GET HTTP/1.1 /" from - "-", referer -'
        assert self.handler.records[1].msg == \
            'Response status 200 in 7 ms, size 13 bytes'

    def test_exception_is_logged(self):
        app = self.wrap_app(error_app)
        with pytest.raises(ZeroDivisionError):
            run_app(app)
        assert self.handler.records[0].msg == \
            'Request "GET HTTP/1.1 /" from - "-", referer -'
        assert self.handler.records[1].msg == 'Exception in 7 ms'
        assert self.handler.records[1].exc_info is not None

    def test_missing_request_context_raises(self):
        app = LoggingMiddleware(simple_app, self.logger)
        with pytest.raises(RuntimeError):
            run_app(app)


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


class TestRequestIDMiddleware(object):
    """Tests `RequestIDMiddleware` class."""

    uuid_re = re.compile(r'^\w{8}-\w{4}-\w{4}-\w{4}-\w{12}$')

    def wrap_app(self, app, **kwargs):
        rv = RequestIDMiddleware(app, **kwargs)
        return RequestContextMiddleware(rv)

    def test_request_id_is_generated(self):
        def test_app(environ, start_response):
            assert self.uuid_re.match(environ['HTTP_X_REQUEST_ID'])
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app)
        response = run_app(app)
        assert response.status_code == 200
        assert self.uuid_re.match(response.headers['X-Request-ID'])

    def test_generated_request_id_is_not_sent_if_disabled(self):
        def test_app(environ, start_response):
            assert self.uuid_re.match(environ['HTTP_X_REQUEST_ID'])
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app, send_request_id=False)
        response = run_app(app)
        assert response.status_code == 200
        assert 'X-Request-ID' not in response.headers

    def test_request_id_is_accepted(self):
        request_id = '2fae06c0-e2c7-46e4-9dfc-019ecd8d6c82'
        def test_app(environ, start_response):
            assert environ['HTTP_X_REQUEST_ID'] == request_id
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app)
        response = run_app(app, headers={'X-Request-ID': request_id})
        assert response.status_code == 200
        assert response.headers['X-Request-ID'] == request_id

    def test_invalid_request_id_is_not_accepted(self):
        def test_app(environ, start_response):
            assert self.uuid_re.match(environ['HTTP_X_REQUEST_ID'])
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app)
        response = run_app(app, headers={'X-Request-ID': 'xxx'})
        assert response.status_code == 200
        assert self.uuid_re.match(response.headers['X-Request-ID'])

    def test_request_id_is_not_accepted_if_disabled(self):
        request_id = '2fae06c0-e2c7-46e4-9dfc-019ecd8d6c82'
        def test_app(environ, start_response):
            assert environ['HTTP_X_REQUEST_ID'] != request_id
            assert self.uuid_re.match(environ['HTTP_X_REQUEST_ID'])
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app, accept_request_id=False)
        response = run_app(app, headers={'X-Request-ID': request_id})
        assert response.status_code == 200
        assert response.headers['X-Request-ID'] != request_id
        assert self.uuid_re.match(response.headers['X-Request-ID'])

    def test_accepted_request_id_is_not_sent_if_disabled(self):
        request_id = '2fae06c0-e2c7-46e4-9dfc-019ecd8d6c82'
        def test_app(environ, start_response):
            assert environ['HTTP_X_REQUEST_ID'] == request_id
            return simple_app(environ, start_response)
        app = self.wrap_app(test_app, send_request_id=False)
        response = run_app(app, headers={'X-Request-ID': request_id})
        assert response.status_code == 200
        assert 'X-Request-ID' not in response.headers

    def test_request_id_is_sent_only_once(self):
        def test_app(environ, start_response):
            extra_headers = [('X-Request-ID', environ['HTTP_X_REQUEST_ID'])]
            return simple_app(environ, start_response,
                              extra_headers=extra_headers)
        app = self.wrap_app(test_app)
        response = run_app(app)
        assert response.status_code == 200
        assert len(response.headers.getlist('X-Request-ID')) == 1

    def test_request_id_is_sent_twice_if_different(self):
        def test_app(environ, start_response):
            extra_headers = [('X-Request-ID', 'xxx')]
            return simple_app(environ, start_response,
                              extra_headers=extra_headers)
        app = self.wrap_app(test_app)
        response = run_app(app)
        assert response.status_code == 200
        assert len(response.headers.getlist('X-Request-ID')) == 2


class TestKudzifyApp(object):
    """Tests `kudzify_app` function"""

    def setup_method(self, method):
        self.handler = HandlerMock()
        self.logger = logging.getLogger('test_middleware')
        self.logger.addHandler(self.handler)
        self.logger.level = logging.DEBUG

    def test_middleware_combindation(self):
        def test_app(environ, start_response):
            assert 'kudzu.context' in environ
            assert 'HTTP_X_REQUEST_ID' in environ
            return simple_app(environ, start_response)
        app = kudzify_app(test_app, logger=self.logger)
        response = run_app(app)
        assert response.status_code == 200
        assert len(self.handler.records) == 2
        assert 'X-Request-ID' in response.headers
