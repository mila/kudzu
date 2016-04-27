
from setuptools import setup

from kudzu import __version__ as version


url = 'https://github.com/mila/kudzu'

def read_description():
    try:
        with open('README.rst', 'rb') as readme:
            rv = readme.read().decode('utf-8')
    except IOError:
        rv = 'See %s' % url
    return rv


setup(
    name='Kudzu',
    version=version,
    url=url,
    author='Miloslav Pojman',
    author_email='miloslav.pojman@gmail.com',
    description='Set of utilities for better logging in WSGI applications',
    long_description=read_description(),
    license='BSD',
    packages=['kudzu'],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Logging',
    ],
    include_package_data=True,
    zip_safe=False,
)
