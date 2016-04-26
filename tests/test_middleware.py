
from __future__ import absolute_import

import logging

import pytest
from werkzeug.test import EnvironBuilder, run_wsgi_app
from werkzeug.wrappers import BaseResponse

from kudzu import LoggingMiddleware, RequestContext, RequestContextMiddleware


class HandlerMock(logging.Handler):
    """Logging handler which saves all logged records."""

    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []
        self.messages = []

    def emit(self, record):
        self.records.append(record)


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
