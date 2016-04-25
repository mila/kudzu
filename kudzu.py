
import logging
import time

try:
    import threading
except ImportError:  # pragma: nocover
    import dummy_threading as threading


#: List of all variables from request context available for logging
CONTEXT_VARS = (
        # http://uwsgi-docs.readthedocs.org/en/latest/LogFormat.html#offsetof
        'uri', 'method', 'user', 'addr', 'host', 'proto', 'uagent', 'referer',
        # http://uwsgi-docs.readthedocs.org/en/latest/LogFormat.html#functions
        'status', 'micros', 'msecs', 'time', 'ctime', 'rsize',
)


def _get_request_uri(environ):
    """Returns REQUEST_URI from WSGI environ

    Environ variable REQUEST_URI is not specified in PEP 333 but provided
    by most servers. This function tries the server generated value and
    fallbacks to reconstruction from variables specified in PEP 333.
    """

    try:
        rv = environ['REQUEST_URI']
    except KeyError:
        parts = [environ.get('SCRIPT_NAME', ''),
                 environ.get('PATH_INFO', '')]
        query = environ.get('QUERY_STRING')
        if query:
            parts.extend(['?', query])
        rv = ''.join(parts)
    return rv


class RequestContext(object):
    """Holds information about one request and corresponding response.

    Instance of this class is created from WSGI environ and later
    updated using arguments passed to `start_response` function.
    """

    _local = threading.local()

    def __init__(self, environ):
        self._start_time = time.time()
        self._log_vars = self._environ_log_vars(environ)

    def __enter__(self):
        self.push()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.pop()

    @staticmethod
    def get():
        """Returns `RequestContext` for the current thread.

        This static method returns `RequestContext` instance which
        is globally available in each thread. Contexts are
        managed in a stack (think of internal redirects) using
        `RequestContext.push` and `RequestContext.pop` methods.

        Returns `None` if the context stack is empty.
        """
        try:
            stack = RequestContext._local.stack
        except AttributeError:
            stack = RequestContext._local.stack = []
        if not stack:
            return None
        return stack[-1]

    @staticmethod
    def reset():
        """Resets any `RequestContext` set for current thread.

        Clears the whole context stack. This method should be avoided
        in favor of `RequestContext.pop`. It is implemented mainly
        to restore global state when testing.
        """
        try:
            del RequestContext._local.stack
        except AttributeError:
            pass

    def push(self):
        """Sets this context for current thread.

        Pushes this instance to the context stack.
        """
        try:
            stack = RequestContext._local.stack
        except AttributeError:
            stack = RequestContext._local.stack = []
        stack.append(self)

    def pop(self):
        """Unsets this context for current thread.

        Pops this instance from the context stack. Raises `RuntimeError`
        if stack is empty or this instance is not at the top.
        """
        try:
            stack = RequestContext._local.stack
        except AttributeError:
            stack = RequestContext._local.stack = []
        if not stack:
            raise RuntimeError('RequestContext stack is empty.')
        if stack[-1] is not self:
            raise RuntimeError('Wrong RequestContext at top of stack.')
        stack.pop()

    @property
    def log_vars(self):
        """Dictionary of variables to be formatted to log messages"""
        duration = time.time() - self._start_time
        rv = self._log_vars.copy()
        rv.update({
            'micros': str(int(duration * 1e6)),
            'msecs': str(int(duration * 1e3)),
            'epoch': str(int(self._start_time)),
        })
        return rv

    def set_status(self, status):
        """Sets response status line.

        This method is called from start_response function.
        """
        try:
            status_code = int(status.split(' ', 1)[0])
        except ValueError:
            self._log_vars['status'] = '???'
        else:
            self._log_vars['status'] = '%s' % status_code

    def set_response_size(self, value):
        """Sets size of response body (without headers) in bytes.

        This method is called if Content-Length header is found
        in start_response function.
        """
        try:
            size = int(value)
        except ValueError:
            self._log_vars['rsize'] = '???'
        else:
            self._log_vars['rsize'] = '%s' % size

    def _environ_log_vars(self, environ):
        rv = dict.fromkeys(CONTEXT_VARS, '-')
        rv.update({
            'uri': _get_request_uri(environ),
            'method': environ['REQUEST_METHOD'],
            'user': environ.get('REMOTE_USER', '-'),
            'addr': environ.get('REMOTE_ADDR', '-'),
            'host': environ.get('HTTP_HOST', environ['SERVER_NAME']),
            'proto': environ['SERVER_PROTOCOL'],
            'uagent': environ.get('HTTP_USER_AGENT', '-'),
            'referer': environ.get('HTTP_REFERER', '-'),
            'time': str(int(self._start_time)),
            'ctime': time.ctime(self._start_time),
        })
        return rv


class RequestContextMiddleware(object):
    """WSGI middleware which creates context instance for each request.

    This middleware creates a `RequestContext` instance for each request
    and makes it globally in the current thread.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if 'kudzu.context' in environ:
            msg = ('RequestContext is already present in environ dictionary.'
                   ' RequestContextMiddleware must be used only once.')
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
            msg = ('RequestContext is not present in environ dictionary.'
                   ' LoggingMiddleware requires RequestContextMiddleware.')
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


class RequestContextFilter(object):
    """Logging filter which injects information about a current request.

    `RequestContextFilter` accepts all log records and extends them by
    contextual information about the current request. Its constructor takes
    names of attributes which should be added to log records.

    This filter should be added to logging handlers not to loggers because
    filters are not executed for records logged by child loggers.

    `RequestContextFilter` depends on `RequestContextMiddleware`
    to make `RequestContext` globally available.

    Functions `augment_handler` and `augment_logger` simplify configuration
    of loggers with this instances of this class.
    """

    def __init__(self, keys):
        self.keys = tuple(keys)

    def filter(self, record):
        context = RequestContext.get()
        log_vars = context.log_vars if context else {}
        for key in self.keys:
            value = log_vars.get(key, '-')
            setattr(record, key, value)
        return True


BASIC_FORMAT = "[%(addr)s] %(levelname)s:%(name)s:%(message)s"


def augment_handler(handler, format=BASIC_FORMAT):
    """Extends format string of a handler by request context placeholders.

    Takes a logging handler instance format string with `CONTEXT_VARS`
    placeholders. It configures `RequestContextFilter` to extract necessary
    variables from a `RequestContext`, attaches the filter to the given
    handler, and replaces handler formatter.
    """
    keys = []
    for key in CONTEXT_VARS:
        if '%%(%s)' % key in format:
            keys.append(key)
    context_filter = RequestContextFilter(keys)
    handler.formatter = logging.Formatter(format)
    handler.addFilter(context_filter)


def augment_logger(logger=None, format=BASIC_FORMAT):
    """Extends format string of a logger by request context placeholders.

    It calls `augment_handler` on each handler registered to the given
    logger. So this function must be called after handlers are configured.
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    for handler in logger.handlers:
        augment_handler(handler, format=format)
