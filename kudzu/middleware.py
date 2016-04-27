
from __future__ import absolute_import

import logging
import re
import uuid

from kudzu.context import RequestContext


uuid_re = re.compile('^[0-9a-f]{8}-?'
                     '[0-9a-f]{4}-?'
                     '[0-9a-f]{4}-?'
                     '[0-9a-f]{4}-?'
                     '[0-9a-f]{12}$')


class LoggingMiddleware(object):
    """WSGI middleware which logs all requests and responses

    Before and after each request this middleware emits messages to
    Python standard logging.

    Requires `RequestContextMiddleware` to be executed before this
    middleware: `app = RequestContextMiddleware(LoggingMiddleware(app))`
    """

    request_format = ('Request "%(method)s %(proto)s %(uri)s" from %(addr)s '
                      '"%(uagent)s", referer %(referer)s')
    response_format = ('Response status %(status)s in %(msecs)s ms, '
                       'size %(rsize)s bytes')
    exception_format = 'Exception in %(msecs)s ms'

    def __init__(self, app, logger='wsgi'):
        self.app = app
        if isinstance(logger, logging.Logger):
            self.logger = logger
        else:
            self.logger = logging.getLogger(logger)

    def __call__(self, environ, start_response):
        try:
            context = environ['kudzu.context']
        except KeyError:
            msg = ('RequestContext is not present in environ dictionary. '
                   'LoggingMiddleware requires RequestContextMiddleware.')
            raise RuntimeError(msg)
        self.log_request(context)
        try:
            rv = self.app(environ, start_response)
        except:
            self.log_exception(context)
            raise
        else:
            self.log_response(context)
        return rv

    def log_request(self, context):
        """Logs request. Can be overridden in subclasses."""
        request_message = self.request_format % context.log_vars
        self.logger.info(request_message)

    def log_response(self, context):
        """Logs response. Can be overridden in subclasses."""
        response_message = self.response_format % context.log_vars
        self.logger.info(response_message)

    def log_exception(self, context):
        """Logs exception. Can be overridden in subclasses."""
        exception_message = self.exception_format % context.log_vars
        self.logger.exception(exception_message)


class RequestContextMiddleware(object):
    """WSGI middleware which creates `RequestContext` for each request.

    This middleware creates a `RequestContext` instance, adds it
    to `environ` and makes it globally in the current thread.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if 'kudzu.context' in environ:
            msg = ('RequestContext is already present in environ dictionary. '
                   'RequestContextMiddleware must be used only once.')
            raise RuntimeError(msg)
        context = environ['kudzu.context'] = RequestContext(environ)
        mw_start_response = self._make_start_response(start_response, context)
        with context:
            rv = self.app(environ, mw_start_response)
        return rv

    def _make_start_response(self, start_response, context):
        """Decorates `start_response` function."""
        return self._StartResponseWrapper(start_response, context)

    class _StartResponseWrapper(object):
        """Decorator which extracts information from response headers"""

        def __init__(self, start_response, context):
            self.start_response = start_response
            self.context = context

        def __call__(self, status, response_headers, exc_info=None):
            self.context.set_status(status)
            for key, value in response_headers:
                if key.upper() == 'CONTENT-LENGTH':
                    self.context.set_response_size(value)
                    break
            return self.start_response(status, response_headers, exc_info)


class RequestIDMiddleware(object):
    """WSGI middleware which adds X-Request-ID to request/response headers

    If `accept_request_id` is truthy (which is default) lookups
    X-Request-ID header in an incoming `environ`. If the value is valid
    it is forwarded to the application. It generates a random UUID and adds it
    to `environ` otherwise.

    If `send_request_id` is truthy (which is default) it adds X-Request-ID
    header to all responses.
    """

    request_id_re = uuid_re

    def __init__(self, app, accept_request_id=True, send_request_id=True):
        self.app = app
        self.accept_request_id = accept_request_id
        self.send_request_id = send_request_id

    def __call__(self, environ, start_response):
        request_id = self._process_environ(environ)
        mw_start_response = self._make_start_response(start_response,
                                                      request_id)
        return self.app(environ, mw_start_response)

    def generate_request_id(self):
        """Generates random request ID"""
        return str(uuid.uuid4())

    def validate_request_id(self, value):
        """Validates incoming request ID"""
        match = self.request_id_re.match(value)
        return bool(match)

    def _process_environ(self, environ):
        """Extracts or inserts request ID from/to WSGI environ."""
        if self.accept_request_id:
            request_id = environ.get('HTTP_X_REQUEST_ID')
            if request_id and self.validate_request_id(request_id):
                return request_id
        request_id = self.generate_request_id()
        environ['HTTP_X_REQUEST_ID'] = request_id
        return request_id

    def _make_start_response(self, start_response, request_id):
        """Decorates `start_response` function to send request ID."""
        if self.send_request_id:
            return self._StartResponseWrapper(start_response, request_id)
        return start_response

    class _StartResponseWrapper(object):
        """Decorator which adds header with request ID"""

        def __init__(self, start_response, request_id):
            self.start_response = start_response
            self.request_id = request_id

        def __call__(self, status, response_headers, exc_info=None):
            for key, value in response_headers:
                if key.upper() == 'X-REQUEST-ID' and value == self.request_id:
                    break
            else:
                header = ('X-Request-ID', self.request_id)
                response_headers.append(header)
            return self.start_response(status, response_headers, exc_info)


def kudzify_app(app, logger='wsgi', accept_request_id=True,
                send_request_id=True):
    """Helper, which applies all Kudzu middlewares to the given application"""
    app = LoggingMiddleware(app, logger=logger)
    app = RequestContextMiddleware(app)
    app = RequestIDMiddleware(app, accept_request_id=accept_request_id,
                              send_request_id=send_request_id)
    return app
