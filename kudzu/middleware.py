
from __future__ import absolute_import

import logging

from kudzu.context import RequestContext


class RequestContextMiddleware(object):
    """WSGI middleware which creates context instance for each request.

    This middleware creates a `RequestContext` instance for each request
    and makes it globally in the current thread.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if 'kudzu.context' in environ:
            msg = ('RequestContext is already present in environ dictionary. '
                   'RequestContextMiddleware must be used only once.')
            raise RuntimeError(msg)
        context = environ['kudzu.context'] = RequestContext(environ)
        mw_start_response = self._wrap_start_response(context, start_response)
        with context:
            rv = self.app(environ, mw_start_response)
        return rv

    def _wrap_start_response(self, context, start_response):
        """Wraps start_response function."""
        def start_response_wrapper(status, response_headers, exc_info=None):
            context.set_status(status)
            for name, value in response_headers:
                if name.lower() == 'content-length':
                    context.set_response_size(value)
                    break
            return start_response(status, response_headers, exc_info)
        return start_response_wrapper


class LoggingMiddleware(object):
    """WSGI middleware which logs all requests and responses

    Before and after each request this middleware emits messages to
    Python standard logging.

    Requires `RequestContextMiddleware` to be executed before this
    middleware:  `RequestContextMiddleware(LoggingMiddleware(app))`
    """

    request_format = ('Request "%(method)s %(proto)s %(uri)s" from %(addr)s, '
                      'user agent "%(uagent)s", referer %(referer)s')
    response_format = ('Response status %(status)s in %(msecs)s ms, '
                       'size %(rsize)s bytes')
    exception_format = 'Exception in %(msecs)s ms.'

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
