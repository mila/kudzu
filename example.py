"""Example application which demonstrates Kudzu functionality.

Run `python example.py`, visit http://localhost:8000/, and follow
log records written to `example.log` file.

Requests and responses are be logged. All emitted log records are
written with remote address and random request ID and the generated
request ID is send to the client in X-Request-ID header.

This is a simple WSGI application without any dependencies.
It can be run using any installed WSGI server.
For example Gunicorn `gunicorn example:application`
or uWSGI `uwsgi --http :8000 --wsgi-file example.py`.
"""

import logging
import math
try:
    from urllib.parse import parse_qs
except ImportError:
    from urlparse import parse_qs

from kudzu import kudzify_app, kudzify_logger, get_request_id


TEMPLATE = u"""
<form>
    <p>ln <input name="x" value="%(x).2f"> = %(y).2f</p>
    <p><input type="submit" value="Compute"></p>
</form>
<p><small>Request ID: %(rid)s</small></p>
"""


def example_app(environ, start_response):
    """Example application. Computes natural logarithm.

    Try to enter invalid values to see exception logged.
    """
    if environ.get('PATH_INFO', '') in ('', '/'):
        q = parse_qs(environ.get('QUERY_STRING', '')).get('x')
        x = float(q[0]) if q else 1
        y = math.log(x)
        # Example log message will be recorded with remote address
        # and request ID.
        logging.getLogger('example').info("ln %s = %s", x, y)
        status = '200 OK'
        # Request is globally available in each thread.
        # Real applications can send when accessing other components.
        request_id = get_request_id()
        response = (TEMPLATE % {'x': x, 'y': y, 'rid': request_id})
    else:
        status = response = '404 Not Found'
    response_headers = [('Content-type', 'text/html'),
                        ('Content-length', '%s' % len(response))]
    start_response(status, response_headers)
    return [response.encode('ascii')]


# Apply Kudzu middlewares to the application.
#
# Function `kudzify_app` is only a helper which applies three wrappers:
# `LoggingMiddleware`, `RequestContextMiddleware` and `RequestIDMiddleware`.
application = kudzify_app(example_app)

# Configure Python logging to write to `example.log` file.
#
# This is only for demonstration purposes, in real application
# any logging handler can be used.
logging.basicConfig(filename='example.log', level=logging.DEBUG)

# Prefix all log records by remote address and request ID.
#
# Function `kudzify_logger` is only a helper which adds
# `RequestContextFilter` to all handlers registered on root logger.
#
# More contextual information can be added, see `kudzu.CONTEXT_VARS`
# for list of all available placeholders.
kudzify_logger(format='[%(addr)s|%(rid)s] %(levelname)s:%(message)s')


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('', 8000, application)
    print("Serving HTTP on port 8000...")
    httpd.serve_forever()
