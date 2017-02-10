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
import elasticsearch
from elasticsearch import Elasticsearch
import filelock
from paapi import PaAuth, PaApi, ApiQueryError

from .tagdb import NCCTagDB

class Coupler:
    """
    Imports data from the PA API into an ElasticSearch database
    """
    elasticsearch = None
    paapi = None
    logfile = None
    loglevel = None
    lockfile = None
    jobtemplates_whitelist = []
    jobtemplates_since = None

    def __init__(self, conf_path, log=None, loglevel=None, lockfile=None):
        config = ConfigParser()
        if not os.path.isfile(conf_path):
            raise Exception("Couldn't open configuration file '%s'" % (conf_path,))
        config.read(conf_path)
        es_hosts = config['elasticsearch']['hosts'].split(',')

        if log is None:
            self.logfile = config['coupler']['logfile']
        if loglevel is None:
            if config['coupler']['loglevel'] == 'ERROR':
                self.loglevel = logging.ERROR
            elif config['coupler']['loglevel'] == 'INFO':
                self.loglevel = logging.INFO
            elif config['coupler']['loglevel'] == 'DEBUG':
                self.loglevel = logging.DEBUG
            else:
                self.loglevel = logging.WARNING
        if lockfile is None:
            self.lockfile = config['coupler']['lockfile']

        # Optional config options.
        try:
            es_username = config['elasticsearch']['username']
            es_password = config['elasticsearch']['password']
            self.elasticsearch = Elasticsearch(
                es_hosts, http_auth=(es_username, es_password), verify_certs=False)
        except KeyError:
            self.elasticsearch = Elasticsearch(es_hosts)

        auth = PaAuth(username=config['pa']['username'],
                      password=config['pa']['password'].strip('"'),
                      basic_auth=config['pa']['basic_auth'].strip('"'))
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
        self.tagdb = NCCTagDB()

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

    def _index(self, force_reindex):
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

    def run(self, force_reindex=False):
        """
        Runs the import as configured.
        """
        log_format = '[%(asctime)s] %(levelname)s: %(message)s'
        logging.basicConfig(filename=self.logfile, level=self.loglevel, format=log_format)

        lock = filelock.FileLock(self.lockfile, timeout=5)
        try:
            with lock:
                self._index(force_reindex)
        except filelock.Timeout:
            logging.critical("Failed to acquire the lock file. Is a process already running?")
            return 2
        logging.info("Finished indexing PA data")
        return 0
