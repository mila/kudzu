# -*- coding: utf-8 -*-

import logging

from kudzu import LoggingMiddleware

logging.basicConfig(level=logging.DEBUG)


def example_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return ['Hello world!\n']


application = LoggingMiddleware(example_app)
