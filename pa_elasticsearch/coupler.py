"""
Reads NCC Performance Analyser data and indexes it in ElasticSearch
"""

#    Copyright 2017 NCC Group plc
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from configparser import ConfigParser
import datetime
import logging
import os.path
import signal
import sys
import time
import elasticsearch
from elasticsearch import Elasticsearch
from paapi import PaAuth, PaApi, ApiQueryError

from .tagdb import NCCTagDB

class Coupler:
    """
    Imports data from the PA API into an ElasticSearch database
    """
    conf_path = None
    elasticsearch = None
    paapi = None
    logfile = None
    loglevel = None
    poll_period = 600 # Default polling period is 10min
    jobtemplates_whitelist = []
    jobtemplates_since = None
    running = True
    polling = False

    def __init__(self, conf_path):
        self.conf_path = conf_path
        self._read_config()
        self.tagdb = NCCTagDB()

    def _read_config(self):
        config = ConfigParser()
        if not os.path.isfile(self.conf_path):
            raise Exception("Couldn't open configuration file '%s'" % (self.conf_path,))
        config.read(self.conf_path)
        es_hosts = config['elasticsearch']['hosts'].split(',')

        if 'logfile' in config['coupler'] and config['coupler']['logfile'].strip() != '':
            self.logfile = config['coupler']['logfile']
        if config['coupler']['loglevel'] == 'ERROR':
            self.loglevel = logging.ERROR
        elif config['coupler']['loglevel'] == 'INFO':
            self.loglevel = logging.INFO
        elif config['coupler']['loglevel'] == 'DEBUG':
            self.loglevel = logging.DEBUG
        else:
            self.loglevel = logging.WARNING

        try:
            self.poll_period = int(config['coupler']['poll_period']) * 60
        except ValueError:
            raise Exception("Couldn't read poll_period from configuration")

        # Optional config options.
        try:
            es_username = config['elasticsearch']['username']
            es_password = config['elasticsearch']['password']
            verify_certs = True
            if 'verify_certs' in config['elasticsearch']:
                verify_certs = not config['elasticsearch']['verify_certs'] == '0'
            from pprint import pprint; pprint(verify_certs)
            self.elasticsearch = Elasticsearch(
                es_hosts, http_auth=(es_username, es_password), verify_certs=verify_certs)
        except KeyError:
            self.elasticsearch = Elasticsearch(es_hosts)

        auth = PaAuth(username=config['pa']['username'],
                      password=config['pa']['password'].strip('"'),
                      client_username=config['pa']['client_username'].strip('"'),
                      client_password=config['pa']['client_password'].strip('"'))
        self.paapi = PaApi(auth, config['pa']['realm'])

        if 'since' in config['pa'] and config['pa']['since'].strip() != '':
            try:
                self.jobtemplates_since = datetime.datetime.strptime(
                    config['pa']['since'],
                    '%Y-%m-%dT%H:%M%z')
            except ValueError:
                raise Exception("Error: couldn't parse the pa.since configuration option")

        if 'jobtemplates' in config['pa'] and config['pa']['jobtemplates'].strip() != '':
            self.jobtemplates_whitelist = config['pa']['jobtemplates'].split(',')

    def _process_jobtemplate_testruns(self, jobtemplate, last_update):
        try:
            testruns = self.paapi.get_testruns_for_jobtemplate(jobtemplate['sref'], last_update)
        except ApiQueryError:
            return
        logging.info('Importing %d testruns from Jobtemplate %s',
                     len(testruns),
                     jobtemplate['sref'])
        for testrun in testruns:
            self._process_testrun_pageobjects(testrun, jobtemplate)

    def _process_testrun_pageobjects(self, testrun, jobtemplate):
        testrun['jobTemplateUri'] = jobtemplate['sref']
        testrun['jobTemplateName'] = jobtemplate['name']
        self.elasticsearch.index(index='pa-testruns',
                                 doc_type='testrun',
                                 id=testrun['sref'],
                                 body=testrun)
        logging.info('Indexed testrun %s', testrun['sref'])
        pageobjects = self.paapi.get_pageobjects_for_testrun(testrun['sref'])
        for pageobject in pageobjects:
            self._process_pageobject(pageobject, testrun, jobtemplate)

    def _process_pageobject(self, pageobject, testrun, jobtemplate):
        pageobject['company'] = 'Unknown'
        pageobject['category'] = 'None'
        pageobject['ranAt'] = testrun['ranAt']
        pageobject['jobTemplateUri'] = jobtemplate['sref']
        pageobject['jobTemplateName'] = jobtemplate['name']
        pageobject['parentUrl'] = testrun['url']
        pageobject['parentPageTitle'] = testrun['pageTitle']
        try:
            domain_info = self.tagdb.get_url_info(pageobject['url'])
            if len(domain_info) > 0:
                company_info = self.tagdb.get_company_info(
                    domain_info[0]['company'],
                    domain_info[0]['product'])
                pageobject['company'] = company_info[0]['name']
                pageobject['category'] = company_info[0]['category']
                logging.info("Retrieved Tag info for %s", pageobject['sref'])
        except Exception as error:
            logging.warning("Failed to retrieve 3rd party info for '%s'", pageobject['url'])
        self.elasticsearch.index(index='pa-objects',
                                 doc_type='pageobject',
                                 id=pageobject['sref'],
                                 body=pageobject)
        logging.info('Indexed pageobject %s', pageobject['sref'])

    def _is_jobtemplate_allowed(self, jobtemplate):
        """
        Checks if jobtemplate is allowed by the configured whitelist.
        """
        if len(self.jobtemplates_whitelist) == 0:
            return True
        return jobtemplate['type'] in self.jobtemplates_whitelist

    def _poll(self, force_reindex):
        logging.info("Polling")
        self.polling = True

        min_date = None
        if force_reindex is False:
            try:
                results = self.elasticsearch.search(index='pa',
                                                    doc_type='testrun',
                                                    sort='ranAt:desc',
                                                    size=1)
                if len(results['hits']['hits']) > 0:
                    last_index = results['hits']['hits'][0]
                    min_date = last_index['_source']['ranAt'].replace('+00:00', 'Z')
                    logging.info("Importing new data from PA")
            except elasticsearch.exceptions.NotFoundError:
                logging.info("No existing data found. Fully indexing from PA")
                min_date = None
            logging.info("Fully indexing data from PA")

        # If no last update could be found, then try to use the one from the config
        if min_date is None and self.jobtemplates_since is not None:
            min_date = self.jobtemplates_since.isoformat()

        jobtemplates = self.paapi.get_all_jobtemplates()
        for jobtemplate in jobtemplates:
            if not self._is_jobtemplate_allowed(jobtemplate):
                continue
            self._process_jobtemplate_testruns(jobtemplate, min_date)

    def os_signal_handler(self, signum, frame):
        "Handles process signals SIGHUP and SIGTERM"
        if signum == signal.SIGHUP:
            logging.info("(SIGHUP) Reloading config")
            self._read_config()
        elif signum == signal.SIGTERM:
            if self.polling:
                logging.info("(SIGTERM) Exiting at next poll")
                self.running = False
            else:
                logging.info("(SIGTERM) Exiting")
                sys.exit(0)

    def run(self, force_reindex=False):
        "Starts polling PA data into Elasticsearch"
        log_format = '[%(asctime)s] %(levelname)s: %(message)s'
        if self.logfile:
            logging.basicConfig(filename=self.logfile, level=self.loglevel, format=log_format)
        else:
            logging.basicConfig(level=self.loglevel, format=log_format)

        signal.signal(signal.SIGHUP, self.os_signal_handler)
        signal.signal(signal.SIGTERM, self.os_signal_handler)

        self.running = True
        self.polling = False
        while self.running:
            started = time.time()
            try:
                self._poll(force_reindex)
            except KeyboardInterrupt:
                logging.info("Aborting from user input")
                return 0
            except Exception as error:
                logging.error(str(error))
            self.polling = False
            # If running was set to false, the sleep is skipped so the program can exit immediately
            if self.running:
                time.sleep(max(0, self.poll_period - (time.time() - started)))
        logging.info("Done, exiting")
