
from __future__ import absolute_import

import logging

from kudzu.context import CONTEXT_VARS, RequestContext


class RequestContextFilter(object):
    """Logging filter which injects information about a current request.

    `RequestContextFilter` accepts all log records and extends them by
    contextual information about the current request. Its constructor takes
    names of attributes which should be added to log records.

    This filter should be added to logging handlers not to loggers because
    filters are not executed for records logged by child loggers.

    `RequestContextFilter` depends on `RequestContextMiddleware`
    to make `RequestContext` globally available.

    Functions `kudzify_handler` and `kudzify_logger` simplify configuration
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


BASIC_FORMAT = "[%(addr)s|%(rid)s] %(levelname)s:%(name)s:%(message)s"


def kudzify_handler(handler, format=BASIC_FORMAT):
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


def kudzify_logger(logger=None, format=BASIC_FORMAT):
    """Extends format string of a logger by request context placeholders.

    It calls `kudzify_handler` on each handler registered to the given
    logger. So this function must be called after handlers are configured.
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    for handler in logger.handlers:
        kudzify_handler(handler, format=format)
