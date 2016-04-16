
import logging
import time
import re

import pytest
from werkzeug.test import Client, EnvironBuilder
from werkzeug.utils import cached_property
from werkzeug.wrappers import BaseResponse

from kudzu import RequestContext, LoggingMiddleware


class HandlerMock(logging.Handler):

    def __init__(self):
        super(HandlerMock, self).__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def simple_app(environ, start_response):
    status = '200 OK'
    data = 'Hello world!\n'
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-length', '%s' % len(data))]
    start_response(status, response_headers)
    return [data]


def error_app(environ, start_response):
    raise Exception('Broken application')


class TestRequestContext(object):

    def test_request_uri_wo_query(self):
        builder = EnvironBuilder(base_url='http://example.com/foo',
                                 path='/bar')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uri'] == '/foo/bar'

    def test_request_uri_w_query(self):
        builder = EnvironBuilder(base_url='http://example.com/foo',
                                 path='/bar?baz=1')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uri'] == '/foo/bar?baz=1'

    def test_method(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['method'] == 'GET'

    def test_remote_user(self):
        builder = EnvironBuilder(environ_base={'REMOTE_USER': 'john.doe'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['user'] == 'john.doe'

    def test_unknown_remote_user(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['user'] == '-'

    def test_remote_addr(self):
        builder = EnvironBuilder(environ_base={'REMOTE_ADDR': '127.0.0.1'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['addr'] == '127.0.0.1'

    def test_unknown_remote_addr(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['addr'] == '-'

    def test_host(self):
        builder = EnvironBuilder(base_url='http://example.com/foo')
        context = RequestContext(builder.get_environ())
        assert context.log_vars['host'] == 'example.com'

    def test_proto(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['proto'] == 'HTTP/1.1'

    def test_user_agent(self):
        builder = EnvironBuilder(headers={'USER_AGENT': 'testbot'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == 'testbot'

    def test_unknown_user_agent(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['uagent'] == '-'

    def test_referer(self):
        builder = EnvironBuilder(headers={'REFERER': 'http://localhost'})
        context = RequestContext(builder.get_environ())
        assert context.log_vars['referer'] == 'http://localhost'

    def test_unknown_referer(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert context.log_vars['referer'] == '-'

    def test_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_status('200 OK')
        assert context.log_vars['status'] == '200'

    def test_invalid_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_status('XXX NOT OK')
        assert context.log_vars['status'] == '???'

    def test_uknown_status(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        # Before start_response was called
        assert context.log_vars['status'] == '-'

    def test_micros(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert 0 <= int(context.log_vars['micros']) < 5000

    def test_msecs(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        assert 0 <= int(context.log_vars['msecs']) < 5

    def test_time(self):
        builder = EnvironBuilder()
        min_time = time.time()
        context = RequestContext(builder.get_environ())
        max_time = time.time()
        assert int(min_time) <= int(context.log_vars['time']) <= int(max_time)

    def test_ctime(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        pattern = r'\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}'
        assert re.match(pattern, context.log_vars['ctime'])

    def test_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_response_size('42')
        assert context.log_vars['rsize'] == '42'

    def test_invalid_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        context.set_response_size('XXX')
        assert context.log_vars['rsize'] == '???'

    def test_unknown_response_size(self):
        builder = EnvironBuilder()
        context = RequestContext(builder.get_environ())
        # No Content-Length header
        assert context.log_vars['rsize'] == '-'


class TestLoggingMiddleware(object):

    @cached_property
    def handler(self):
        return HandlerMock()

    @cached_property
    def logger(self):
        logger = logging.Logger('test')
        logger.addHandler(self.handler)
        return logger

    @cached_property
    def middleware(self):
        rv = LoggingMiddleware(simple_app, self.logger)
        # Fake response time in log messages
        rv.response_format = rv.response_format.replace('%(msecs)s', '7')
        rv.exception_format = rv.exception_format.replace('%(msecs)s', '7')
        return rv

    @cached_property
    def client(self):
        return Client(self.middleware, BaseResponse)

    def test_request_and_response_are_logged(self):
        response = self.client.get('/')
        assert response.status_code == 200
        assert len(self.handler.records) == 2
        assert self.handler.records[0].msg == \
            'Request "GET HTTP/1.1 /" from -, user agent "-", referer -'
        assert self.handler.records[1].msg == \
            'Response status 200 in 7 ms, size 13 bytes'

    def test_exception_is_logged(self):
        self.middleware.app = error_app
        with pytest.raises(Exception):
            self.client.get('/')
        assert self.handler.records[0].msg == \
            'Request "GET HTTP/1.1 /" from -, user agent "-", referer -'
        assert self.handler.records[1].msg == 'Exception in 7 ms.'
        assert self.handler.records[1].exc_info is not None
