
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
    ],
    include_package_data=True,
    zip_safe=False,
)
