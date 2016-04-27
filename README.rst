Kudzu - set of utilities for better logging in Python applications
==================================================================

Kudzu provides WSGI middleware and logging handlers which:

 - Read or generate unique ID for each request and include this
   request ID in emitted log records.
 - Sends request ID in response using X-Request-ID header.
   This ID is also  made globally available and can included when
   calling other applications or components.
 - Logs all requests and responses using Python standard logging.


Kudzu is framework independent and it is compatible with both
Python 2 (tested with 2.6 and 2.7) and Python 3 (tested with 3.3 and 3.4).


Installation
------------

Kudzu can be installed using pip_ (or easy_install) from PyPI: ::

    $ pip install kudzu

Alternatively you can download and extract tarball and install the package manually: ::

    $ python setup.py install

Placing the package to your PYTHONPATH should also work.


Example usage
-------------

::

    # Apply middleware to WSGI application
    application = kudzify_app(application)

    # Include request ID and remote address in log records
    kudzify_logger(format='[%(addr)s|%(rid)s] %(levelname)s:%(message)s')


See `example.py` for more information.


Testing
-------

Tests for all supported Python versions can be run using Tox_: ::

    $ tox

Alternativelly you can install Kudzu with test dependencies pytest
and `Werkzeug` and run tests manually: ::

    $ py.test


.. _pip: https://pypi.python.org/pypi/pip
.. _Tox: https://testrun.org/tox/latest/
