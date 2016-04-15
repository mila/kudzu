
import logging
from wsgiref.simple_server import demo_app

from werkzeug.test import Client

from kudzu import LoggingMiddleware


class TestHandler(logging.Handler):

    def __init__(self):
        super(TestHandler, self).__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class TestLoggingMiddleware(object):

    def test_records_are_logged(self):
        handler = TestHandler()
        logger = logging.Logger('test')
        logger.addHandler(handler)
        app = LoggingMiddleware(demo_app, logger)
        c = Client(app)
        _, status, _ = c.get('/')
        assert status == '200 OK'
        assert len(handler.records) == 2
