"""
Abstracts access to the Tag DB
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

import json
from urllib.parse import urlparse, quote
import urllib3

# Suppress custom SSL certificates warning. Otherwise they're printed once per endpoint call.
urllib3.disable_warnings()

class NCCTagDB(object):
    """
    Abstraction of the NCC Tag db
    """
    api_url = 'https://ncctagdb.herokuapp.com/2'
    known_domains = {}
    known_companies = {}

    def __init__(self):
        self.http = urllib3.PoolManager()

    def _query_api(self, method, url, fields=None, headers=None):
        """
        Abstracts http queries to the API
        """
        response = self.http.request(method, url, fields, headers)
        if response.status != 200:
            raise Exception("Failed to get API data")
        return json.loads(response.data.decode())

    def get_domain_info(self, domain):
        """
        Retrieves third party data from a domain
        """
        if domain in self.known_domains:
            return self.known_domains[domain]
        endpoint = '%s/tag?domain=%s' % (self.api_url, quote(domain))
        data = self._query_api('GET', endpoint)
        self.known_domains[domain] = data
        return data

    def get_url_info(self, url):
        """
        Retrieves domain 3rd party info from a given URL.
        """
        parsed_uri = urlparse(url)
        return self.get_domain_info(parsed_uri.netloc)

    def get_company_info(self, company, product):
        """
        Retrives company info; category etc.
        """
        key = '%s-%s' % (company, product)
        if key in self.known_companies:
            return self.known_companies[key]
        endpoint = '%s/product?company=%s&name=%s' % (self.api_url, quote(company), quote(product))
        data = self._query_api('GET', endpoint)
        self.known_companies[key] = data
        return data
