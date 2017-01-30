#!/usr/bin/env python3

"""NCC Performance Analyser API to ElasticSearch coupler"""

import os
from setuptools import setup, find_packages
from pip.req import parse_requirements

reqs_path = os.path.dirname(os.path.realpath(__file__)) + '/requirements.txt'
install_reqs = parse_requirements(reqs_path, session=False)
requires = [str(ir.req) for ir in install_reqs]

setup(
    name='pacoupler',
    description='PA to ElasticSearch coupler',
    author='NCC Group',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    scripts=['bin/pa-es-coupler.py'],
    install_requires=requires
)
