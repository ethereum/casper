#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


def check_setuptools_features():
    import pkg_resources
    try:
        list(pkg_resources.parse_requirements('foo~=1.0'))
    except ValueError:
        exit('Your Python distribution comes with an incompatible version '
             'of `setuptools`. Please run:\n'
             'pip install --upgrade setuptools\n'
             'and then run this command again')


# check if setuptools is up to date
check_setuptools_features()

# requirements
install_requires = set(x.strip() for x in open('requirements.txt'))
install_requires_replacements = {
    'https://github.com/ethereum/pyrlp/tarball/develop/': 'rlp',
    'https://github.com/ethereum/pyethereum/tarball/develop': 'ethereum',
}
install_requires = [install_requires_replacements.get(r, r) for r in install_requires]

# dependency links
dependency_links = [
    'https://github.com/ethereum/pyrlp/tarball/develop/#egg=rlp-9.99.9',
    'https://github.com/ethereum/pyethereum/tarball/develop#egg=ethereum-9.99.9'
]

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
# see: https://github.com/ethereum/pyethapp/wiki/Development:-Versions-and-Releases
version = '0.0.1'

setup(
    name='casper',
    version=version,
    description='A proof of stake protocol for Ethereum',
    author='Ethereum Foundation',
    author_email='info@ethereum.org',
    url='https://github.com/ethereum/casper',
    packages=[
        'casper',
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
        'Programming Language :: Python :: 3.6',
    ],
    cmdclass={'test': PyTest},
    install_requires=install_requires,
    dependency_links=dependency_links,
    tests_require=[],
    entry_points='''
    [console_scripts]
    casper=casper.daemon.app:app
    '''
)
