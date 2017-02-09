NCC PA Elasticsearch Coupler
============================

## Description
This is a little poller that will index Performance Analyser data into ElasticSearch
so it can be filtered and reported on later.

## Dependencies
The base system needs to have Python3.5+ installed. Using virtualenv or venv is recommended.
The following dependencies are fetched as part of the installation:

- elasticsearch
- filelock
- urllib3
- ncc_paapi

## Install

To install the coupler system wide, follow the pypi method without
creating a venv. Note that you may need to run `pip` as root (or with sudo).

To create a venv, proceed like so:

```
python3 -m venv venv
source venv/bin/activate
```
(This does not work with the fish shell).

### From Pypi

```
pip install ncc_pa_elasticsearch
```

### From source

Change to the coupler's folder. Then install it like so:

```
pip install .
```

## Configuration
You will need to configure how to access the elasticsearch server and the PA API.
Copy the file `config-example.ini` to `config.ini` and follow the commented
instructions to configure access to your services.

## Usage
Add a crontab entry to run every minute (or less frequently if you want) like so:

```
* * * * * /<path-to-venv>/bin/python3 /<path-to-venv>/bin/pa-es-coupler.py --config <path-to-config>/config.ini
```
