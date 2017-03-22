#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def __init__(self, *args, **kwargs):
        TestCommand.__init__(self, *args, **kwargs)
        self.test_suite = True

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        raise SystemExit(errno)


INSTALL_REQUIRES_REPLACEMENTS = {}
INSTALL_REQUIRES = list()
with open('requirements.txt') as requirements_file:
    for requirement in requirements_file:
        # install_requires will break on git URLs, so skip them
        if 'git+' in requirement:
            continue
        dependency = INSTALL_REQUIRES_REPLACEMENTS.get(
            requirement.strip(),
            requirement.strip(),
        )

        INSTALL_REQUIRES.append(dependency)

INSTALL_REQUIRES = list(set(INSTALL_REQUIRES))

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
# see: https://github.com/ethereum/pyethapp/wiki/Development:-Versions-and-Releases
version = '0.0.1'

setup(
    name='simplecasper',
    version=version,
    description='Ethereum Casper POC4 Daemon',
    long_description="Ethereum Casper POC4 Daemon",
    author='Jan Xie',
    author_email='jan.h.xie@gmail.com',
    url='https://github.com/cryptape/simplecasper',
    packages=[
        'simplecasper',
    ],
    package_data={},
    license='MIT',
    zip_safe=False,
    keywords=[
        'ethereum',
        'consensus',
        'casper'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    cmdclass={'test': PyTest},
    install_requires=INSTALL_REQUIRES,
    tests_require=[],
    entry_points='''
    [console_scripts]
    simplecasper=simplecasper.app:app
    '''
)
