# -*- coding: utf-8 -*-

import logging
from wsgiref.simple_server import make_server
from wsgiref.validate import validator
from kudzu import LoggingMiddleware, RequestContextMiddleware

logging.basicConfig(level=logging.DEBUG)


def example_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return ['Hello world!\n']


application = example_app
application = validator(application)
application = LoggingMiddleware(application)
application = RequestContextMiddleware(application)
application = validator(application)


if __name__ == '__main__':
    httpd = make_server('', 8000, application)
    print "Serving HTTP on port 8000..."
    httpd.serve_forever()
