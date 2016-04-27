
from __future__ import absolute_import

import logging

from werkzeug.test import EnvironBuilder

from kudzu import RequestContext, kudzify_handler, kudzify_logger


class HandlerMock(logging.Handler):
    """Logging handler which saves all logged messages."""

    def __init__(self):
        logging.Handler.__init__(self)
        self.messages = []

    def emit(self, record):
        self.messages.append(self.format(record))


class TestRequestContextFilter(object):

    format = '["%(method)s %(proto)s %(uri)s" from %(addr)s] %(message)s'

    def setup_method(self, method):
        self.handler = HandlerMock()
        self.logger = logging.getLogger('test_logging')
        self.logger.addHandler(self.handler)
        self.logger.level = logging.DEBUG

    def teardown_method(self, method):
        self.logger.removeHandler(self.handler)

    def test_kudzify_handler(self):
        kudzify_handler(self.handler, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_kudzify_logger(self):
        kudzify_logger(self.logger, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_kudzify_logger_by_name(self):
        kudzify_logger(self.logger.name, format=self.format)
        builder = EnvironBuilder()
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /" from -] Hello Kudzu'

    def test_log_wo_context(self):
        kudzify_logger(self.logger, format=self.format)
        self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == '["- - -" from -] Hello Kudzu'

    def test_log_w_context(self):
        kudzify_logger(self.logger, format=self.format)
        builder = EnvironBuilder(path='/foo',
                                 environ_base={'REMOTE_ADDR': '127.0.0.1'})
        with RequestContext(builder.get_environ()):
            self.logger.info('Hello %s', 'Kudzu')
        assert len(self.handler.messages) == 1
        assert self.handler.messages[0] == \
            '["GET HTTP/1.1 /foo" from 127.0.0.1] Hello Kudzu'
