from configparser import ConfigParser
import elasticsearch
from elasticsearch import Elasticsearch
import logging
import filelock

from .paapi import PaApi
from .tagdb import NCCTagDB

class Coupler:
    """
    Imports data from the PA API into an ElasticSearch database
    """
    es = None
    paapi = None
    logfile = None
    loglevel = None
    lockfile = None

    def _sref_to_id(self, obj):
        """
        Converts a PA sref to only the numerical ID part.
        """
        return int(obj['sref'].split('/')[1])

    def __init__(self, conf_path, log=None, loglevel=None, lockfile=None):
        config = ConfigParser()
        config.read(conf_path)

        es_hosts = config['elasticsearch']['hosts'].split(',')

        if log is None:
            self.logfile = config['coupler']['logfile']
        if loglevel is None:
            if config['coupler']['loglevel'] == "ERROR":
                self.loglevel = logging.ERROR
            elif config['coupler']['loglevel'] == "INFO":
                self.loglevel = logging.INFO
            else:
                self.loglevel = logging.WARNING
        if lockfile is None:
            self.lockfile = config['coupler']['lockfile']

        # Optional config options.
        try:
            es_username = config['elasticsearch']['username']
            es_password = config['elasticsearch']['password']
            self.es = Elasticsearch(es_hosts, http_auth=(es_username, es_password), verify_certs=False)
        except KeyError:
            self.es = Elasticsearch(es_hosts)

        self.paapi = PaApi( base_url = config['pa']['endpoint'],
                            username = config['pa']['username'],
                            password = config['pa']['password'],
                            auth = config['pa']['basic_auth'],
                            realm = config['pa']['realm'] )

        self.tagdb = NCCTagDB()

    def _process_jobtemplate_testruns(self, jobtemplate, last_update):
        jt_id = self._sref_to_id(jobtemplate)
        testruns = self.paapi.get_testruns_for_jobtemplate(jt_id, last_update)
        logging.info('Importing %d testruns from Jobtemplate %d' % (len(testruns), jt_id))
        for testrun in testruns: self._process_testrun_pageobjects(testrun, jobtemplate)

    def _process_testrun_pageobjects(self, testrun, jobtemplate):
        tr_id = self._sref_to_id(testrun)
        testrun['jobTemplateUri'] = jobtemplate['sref']
        testrun['jobTemplateName'] = jobtemplate['name']
        self.es.index(index='pa-testruns', doc_type='testrun', id=tr_id, body=testrun)

        pageobjects = self.paapi.get_pageobjects_for_testrun(tr_id)
        for pageobject in pageobjects: self._process_pageobject(pageobject, testrun, jobtemplate)

    def _process_pageobject(self, pageobject, testrun, jobtemplate):
        po_id = self._sref_to_id(pageobject)
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
                    domain_info[0]['product']
                )
                pageobject['company'] = company_info[0]['name']
                pageobject['category'] = company_info[0]['category']
        except Exception as e:
            logging.warning("Failed to retrieve 3rd party info for '%s'" % (pageobject['url'],))
        self.es.index(index='pa-objects', doc_type='pageobject', id=po_id, body=pageobject)

    def index(self, force_reindex):
        last_update = None
        if force_reindex is False:
            try:
                results = self.es.search(index='pa', doc_type='testrun', sort='ranAt:desc', size=1)
                if len(results['hits']['hits']) > 0:
                    last_update = results['hits']['hits'][0]['_source']['ranAt'].replace('+00:00', 'Z')
                    logging.info("Importing new data from PA")
            except elasticsearch.exceptions.NotFoundError:
                logging.info("No existing data found. Fully indexing from PA")
                last_update = None
        else:
            logging.info("Fully indexing data from PA")

        self.paapi.authenticate()
        logging.info("Authenticated with PA API")
        jobtemplates = self.paapi.get_all_jobtemplates()
        for jobtemplate in jobtemplates: self._process_jobtemplate_testruns(jobtemplate, last_update)

    def run(self, force_reindex=False):
        """
        Runs the import as configured.
        """
        log_format='[%(asctime)s] %(levelname)s: %(message)s'
        logging.basicConfig(filename=self.logfile, level=self.loglevel, format=log_format)

        lock = filelock.FileLock(self.lockfile, timeout=5)
        try:
            with lock:
                self.index(force_reindex)
        except filelock.Timeout:
            logging.critical("Failed to acquire the lock file. Is a process already running?")
            return 2
        logging.info("Finished indexing PA data")
        return 0
