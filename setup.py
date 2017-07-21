#!/usr/bin/env python3

"""NCC Performance Analyser API to ElasticSearch coupler"""

from setuptools import setup

setup(
    name='ncc_pa_elasticsearch',
    version='0.0.7',
    description='PA to ElasticSearch coupler',
    author='NCC Group',
    packages=['pa_elasticsearch'],
    scripts=['bin/pa-es-coupler.py'],
    license="Apache License 2.0",
    install_requires=[
        'elasticsearch==5.1.0',
        'urllib3==1.19.1',
        'ncc_paapi==0.0.7'
    ],
    url='https://github.com/ncc-tools/pa-elasticsearch-coupler'
)
