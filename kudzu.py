# -*- coding: utf-8 -*-

import time
import logging


def _get_request_uri(environ):
    """Returns REQUEST_URI from WSGI environ

    Environ variable REQUEST_URI is not specified in PEP 333 but provided
    by most servers. This function tries the server generated value and
    fallbacks to reconstruction from variables specified in PEP 333.
    """

    try:
        rv = environ['REQUEST_URI']
    except KeyError:
        rv = ''.join([environ.get('SCRIPT_NAME', ''),
                      environ.get('PATH_INFO', ''),
                      environ.get('QUERY_STRING', '')])
    return rv


class RequestContext(object):
    """Holds information about one request and corresponding response.

    Instance of this class is created from WSGI environ and later
    updated using arguments passed to `start_response` function.
    """

    def __init__(self, environ):
        self._start_time = time.time()
        self._log_vars = self._environ_log_vars(environ)

    @property
    def log_vars(self):
        """Dictionary of variables to be formatted to log messages"""
        duration = time.time() - self._start_time
        rv = self._log_vars.copy()
        rv.update({
            'micros': int(duration * 1e6),
            'msecs': int(duration * 1e3),
            'epoch': int(self._start_time),
        })
        return rv

    def set_status(self, status):
        """Sets response status line."""
        self._log_vars['status'] = status.split(' ', 1)[0]

    def set_response_size(self, value):
        """Sets size of response body (without headers) in bytes."""
        self._log_vars['rsize'] = value

    def _environ_log_vars(self, environ):
        rv = {
            # http://uwsgi-docs.readthedocs.org/en/latest/LogFormat.html#offsetof
            'uri': _get_request_uri(environ),
            'method': environ['REQUEST_METHOD'],
            'user': environ.get('REMOTE_USER', '-'),
            'addr': environ.get('REMOTE_ADDR', '-'),
            'host': environ.get('HTTP_HOST', environ['SERVER_NAME']),
            'proto': environ['SERVER_PROTOCOL'],
            'uagent': environ.get('HTTP_USER_AGENT', '-'),
            'referer': environ.get('HTTP_REFERER', '-'),
            # http://uwsgi-docs.readthedocs.org/en/latest/LogFormat.html#functions
            'status': '-',
            'micros': '-',
            'msecs': '-',
            'time': str(self._start_time),
            'ctime': time.ctime(self._start_time),
            'rsize': '?',
        }
        return rv


class LoggingMiddleware(object):
    """
    WSGI middleware which logs all requests and responses
    """

    request_format = ('Request "%(method)s %(proto)s %(uri)s" from %(addr)s, '
                      'user agent "%(uagent)s", referer %(referer)s')
    response_format = ('Response status %(status)s in %(msecs)s ms, '
                       'size %(rsize)s bytes')
    exception_format = 'Exception in %(msecs)s ms.'

    def __init__(self, app, logger='wsgi'):
        self.app = app
        if isinstance(logger, basestring):
            self.logger = logging.getLogger(logger)
        else:
            self.logger = logger

    def __call__(self, environ, start_response):
        context = RequestContext(environ)
        self.log_request(context)
        wrapper = self.wrap_start_response(context, start_response)
        try:
            rv = self.app(environ, wrapper)
        except:
            self.log_exception(context)
            raise
        self.log_response(context)
        return rv

    def wrap_start_response(self, context, start_response):
        def start_response_wrapper(status, response_headers, exc_info=None):
            context.set_status(status)
            for name, value in response_headers:
                if name.lower() == 'content-length':
                    context.set_response_size(value)
                    break
            return start_response(status, response_headers, exc_info)
        return start_response_wrapper

    def log_request(self, context):
        request_message = self.request_format % context.log_vars
        self.logger.info(request_message)

    def log_response(self, context):
        response_message = self.response_format % context.log_vars
        self.logger.info(response_message)

    def log_exception(self, context):
        exception_message = self.exception_format % context.log_vars
        self.logger.exception(exception_message)
