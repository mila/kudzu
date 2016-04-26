"""Example application which demonstrates Kudzu functionality.

Run `python example.py`, visit http://localhost:8000/, and follow
log records written to `example.log` file.

Requests and responses should be logged. Records emitted by all
loggers are prefixed by remote address and requested URI.

Any installed WSGI server will do the job. You can try
`gunicorn example:application` or `uwsgi --http :8000 --wsgi-file example.py`
"""

import logging
import math
try:
    from urllib.parse import parse_qs
except ImportError:
    from urlparse import parse_qs

from kudzu import augment_logger, LoggingMiddleware, RequestContextMiddleware


TEMPLATE = u"""
<form>
    <p>ln <input name="x" value="%(x).2f"> = %(y).2f</p>
    <p><input type="submit" value="Compute"></p>
</form>
"""


def example_app(environ, start_response):
    """Example application. Computes natural logarithm.

    Try to enter invalid values to see exception logged.
    """
    if environ.get('PATH_INFO', '') in ('', '/'):
        q = parse_qs(environ.get('QUERY_STRING', '')).get('x')
        x = float(q[0]) if q else 1
        y = math.log(x)
        logging.getLogger('example').info("ln %s = %s", x, y)
        status = '200 OK'
        response = (TEMPLATE % {'x': x, 'y': y})
    else:
        status = response = '404 Not Found'
    data = response.encode('ascii')
    response_headers = [('Content-type', 'text/html'),
                        ('Content-length', '%s' % len(data))]
    start_response(status, response_headers)
    return [data]

# Configure Python logging to write to `example.log` file.
logging.basicConfig(filename='example.log', level=logging.DEBUG)
# Add remote address and requested URI to all log records.
# See `kudzu.CONTEXT_VARS` for available placeholders.
augment_logger(format="[%(addr)s at %(uri)s] %(levelname)s:%(message)s")

application = example_app
# Log all requests and responses.
application = LoggingMiddleware(application)
# Construct RequestContext for each request. Required
# by both `LoggingMiddleware` and `augment_logger`.
application = RequestContextMiddleware(application)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('', 8000, application)
    print("Serving HTTP on port 8000...")
    httpd.serve_forever()
