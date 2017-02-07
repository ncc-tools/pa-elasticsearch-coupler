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

import urllib3
import json

# Suppress custom SSL certificates warning. Otherwise they're printed once per endpoint call.
urllib3.disable_warnings()

class PaApi(object):
    """
    Abstraction to access the PA API
    """
    base_url = 'https://paapi.siteconfidence.co.uk'
    api_url = base_url + '/pa/1'
    username = None
    password = None
    basic_auth = None
    http = None
    page_size = 1000

    auth_token = None
    auth_realm = '617523'

    def __init__(self, base_url, username, password, auth, realm):
        self.base_url = base_url
        self.api_url = '%s/pa/1' % (self.base_url,)
        self.username = username.strip('"')
        self.password = password.strip('"')
        self.basic_auth = auth.strip('"')
        self.auth_realm = realm
        self.http = urllib3.PoolManager()

    def authenticate(self):
        """
        Authenticates the API. Always call this before anything else.
        """
        response = self.http.request(
            'POST',
            '%s/authorisation/token' % (self.base_url,),
            {
                'username': self.username,
                'password': self.password,
                'grant_type': 'password'
            },
            {
                'Authorization': 'Basic %s' % (self.basic_auth,)
            }
        )

        if response.status != 200:
            raise Exception("Couldn't authenticate to PA API")

        data = json.loads(response.data.decode())
        self.auth_token = data['access_token']
        return response

    def _query_api(self, method, url, fields=None, headers=None):
        """
        Abstracts http queries to the API
        """
        if headers is None:
            headers = {}
        if 'Authorization' not in headers:
            headers['Authorization'] = 'Bearer %s' % (self.auth_token,)
        if 'Realm' not in headers:
            headers['Realm'] = self.auth_realm
        response = self.http.request(method, url, fields, headers)
        if response.status != 200:
            raise Exception("Failed to get API data")
        return json.loads(response.data.decode())

    def get_all_jobtemplates(self):
        """
        Retrieves the list of jobTemplates for the current realm.
        """
        endpoint = '%s/jobTemplates?paginationPageSize=%d' % (self.api_url, self.page_size)
        data = self._query_api('GET', endpoint)
        return data['results']

    def get_testruns_for_jobtemplate(self, jobtemplate_id, start_date=None):
        """
        Retrieves a bunch of test runs for a specific job template.
        """
        if start_date is not None:
            endpoint = '%s/testRuns?jobTemplate=jobTemplates/%d&fromDate=%s&paginationPageSize=%d' % (self.api_url, jobtemplate_id, start_date, self.page_size)
        else:
            endpoint = '%s/testRuns?jobTemplate=jobTemplates/%d&paginationPageSize=%d' % (self.api_url, jobtemplate_id, self.page_size)
        data = self._query_api('GET', endpoint)
        return data['results']

    def get_pageobjects_for_testrun(self, testrun_id):
        """
        Retrieves pageobject data for a particular testrun.
        """
        endpoint = '%s/objects?testRun=testRuns/%d&paginationPageSize=%d' % (self.api_url, testrun_id, self.page_size)
        data = self._query_api('GET', endpoint)
        return data['results']
