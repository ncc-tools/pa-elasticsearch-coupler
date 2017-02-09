#!/usr/bin/env python3

"""NCC Performance Analyser API to ElasticSearch coupler"""

from setuptools import setup

setup(
    name='ncc_pa_elasticsearch',
    version='0.0.1',
    description='PA to ElasticSearch coupler',
    author='NCC Group',
    packages=['pa_elasticsearch'],
    scripts=['bin/pa-es-coupler.py'],
    install_requires=[
        'elasticsearch==5.1.0',
        'filelock==2.0.7',
        'urllib3==1.19.1',
        'ncc_paapi==0.0.3'
    ],
    url='https://github.com/ncc-tools/pa-elasticsearch-coupler'
)
