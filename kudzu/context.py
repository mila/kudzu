
from __future__ import absolute_import

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
    'status', 'micros', 'msecs', 'time', 'ctime', 'epoch', 'rsize',
    # Custom
    'rid',
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

    @property
    def remote_addr(self):
        """Remote address of this context request"""
        addr = self._log_vars['addr']
        if addr == '-':
            return None
        return addr

    @property
    def request_id(self):
        """Request ID  of this context request"""
        rid = self._log_vars['rid']
        if rid == '-':
            return None
        return rid

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
        get_env_var = environ.get
        rv.update({
            'uri': _get_request_uri(environ),
            'method': environ['REQUEST_METHOD'],
            'user': get_env_var('REMOTE_USER', '-'),
            'addr': get_env_var('REMOTE_ADDR', '-'),
            'host': get_env_var('HTTP_HOST', environ['SERVER_NAME']),
            'proto': environ['SERVER_PROTOCOL'],
            'uagent': get_env_var('HTTP_USER_AGENT', '-'),
            'referer': get_env_var('HTTP_REFERER', '-'),
            'time': str(int(self._start_time)),
            'ctime': time.ctime(self._start_time),
            'rid': get_env_var('HTTP_X_REQUEST_ID', '-'),
        })
        return rv


def get_remote_addr():
    """Returns remote address of the the current thread request.

    Returns None, if no `RequestContext` was pushed at the stack
    or if remote address is not known.
    """
    context = RequestContext.get()
    if context is None:
        return None
    return context.remote_addr


def get_request_id():
    """Returns request ID of the the current thread request.

    Returns None, if no `RequestContext` was pushed at the stack
    or if request ID is not known.
    """
    context = RequestContext.get()
    if context is None:
        return None
    return context.request_id
