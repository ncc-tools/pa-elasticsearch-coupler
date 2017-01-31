PA ELASTICSEARCH COUPLER
========================

## DESCRIPTION
This is a little poller that will index PA data into ElasticSearch so it can be
analysed and report on later.

## DEPENDENCIES
The base system needs to have Python3.5+ installed. Pyvenv is recommended.

## INSTALL
Create your venv somewhere like so:

```
python3 -m venv venv
source venv/bin/activate
```
(This does not work with the fish shell).

Change to the coupler's folder. Then install it like so:

```
pip install .
```

## CONFIGURATION
You will need to configure how to access the elasticsearch server and the PA API.
Copy the file `config-example.ini` to `config.ini` and follow the commented
instructions to configure access to your services.

## USAGE
Add a crontab entry to run every minute (or less frequently if you want) like so:

```
* * * * * /<path-to-venv>/bin/python3 /<path-to-venv>/bin/pa-es-coupler.py -c <path-to-config>/config.ini
```
