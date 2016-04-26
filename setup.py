
from setuptools import setup


url = 'https://github.com/mila/kudzu'

try:
    with open('README.rst', 'rb') as readme:
        long_description = readme.read().decode('utf-8')
except IOError:
    long_description = 'See %s' % url


setup(
    name='Kudzu',
    version='0.1-dev',
    url=url,
    author='Miloslav Pojman',
    author_email='miloslav.pojman@gmail.com',
    description='Set of utilities for better logging in WSGI applications',
    long_description=long_description,
    license='BSD',
    packages=['kudzu'],
    classifiers=[
    ],
    include_package_data=True,
    zip_safe=False,
)
