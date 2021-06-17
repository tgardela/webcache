import base64
import bz2
import json
import os
import pickle

import requests

from helpers import dbNormalizeURL, isValidURL


class WebCacheClient: # add constructor to set webcache location programmatically. fall back to config if no explicit location provided
    WEBCACHE_LOCATION = "10.5.133.201:9011" 

    def __init__(self):
        expectedEnvLocation = "%s/.labscape.env" % os.path.expanduser("~") #it's probably better to specify the webcache IP in the file rather than the env name
        if os.path.exists(expectedEnvLocation):
            with open(expectedEnvLocation, "r") as fi:
                content = fi.read()
                if content.strip().lower() == "dev":
                    print("using DEV-environment for cache")
                    self.WEBCACHE_LOCATION = "localhost:9011"

                if content.strip().lower() == "docker":
                    print("using docker-environment for cache")
                    self.WEBCACHE_LOCATION = "webcache:9011"

    def getProxyList(self, numProxies: int = 1000):
        '''
        gets list of proxies from data service. Some of the proxies might not work, but the probability of having a
        majority of good proxies is rather high.
        :param numProxies: maximal number of proxies returned (the higher the number of proxies, the larger the share of non-working proxies. Usually you can expect there to be around 1500 working proxies in the service at any given time)
        :return: list of proxies
        '''
        if type(numProxies) != int:
            raise ValueError("numProxies must be an integer")

        if numProxies < 1:
            return []
        else:
            serviceURL = "http://%s/proxies/%s" % (self.WEBCACHE_LOCATION, numProxies)
            data = requests.get(serviceURL).json()
            if data is not None and "response" in data:
                return data["response"]
            else:
                raise ValueError("could not get proxies: %s" % data)

    def fetchURLs(self, urlList, category:str, output, method="GET", maxAgeDays=360):
        '''
        uses data service to fetch a list of urls

        :param urlList: non-empty list of url's to be obtained. if data is included in a POST request -> list of tuples(url, data-json)
        :param category: name of the dataprocessor issuing request and type of request. Example: "dataprocessor_geocoder:find-latlon". Only for logging purposes
        :param output: how should the cache output be interpreted and serialised? supported are JSON and XML (BeautifulSoup object returned)
        :param method: GET/POST
        :param maxAgeDays: maximum age of page in cache in days. If a URL has been cached longer ago than these days, it is fetched again
        :return: dictionary where input url's are mapped to cache-result. available fields in cache-result-dict: content, size, url, format, creation_date, urlKey
        '''
        if output.lower() not in ["json", "xml"]:
            raise ValueError("output-field must be either JSON or XML")

        if method.upper() not in ["GET", "POST"]:
            raise ValueError("the web cache currently only supports GET and POST Requests")

        filteredUrlList = []
        for urlItem in urlList:
            urlTuple = (urlItem, '{}') if type(urlItem) is str else urlItem

            if isValidURL(urlTuple[0]):
                filteredUrlList.append(urlTuple)
            else:
                print("invalid URL supplied to cache: %s. will ignore it" % urlTuple[0])

        serviceURL = "http://%s/fetch/%s/%s/%s/%s" % (self.WEBCACHE_LOCATION, maxAgeDays, category, output, method)
        if any('localhost' in url[0] or '127.0.0.1' in url[0] for url in filteredUrlList):
            data = {}
            for url in filteredUrlList:
                data[url[0]] = {'content':requests.get(url[0]).json()}
            return data
        else:
            data = requests.post(serviceURL, {"urls": json.dumps(filteredUrlList)}).json()

        if "error" in data:
            raise ValueError("cache could not obtain data. Error: %s" % data["error"])
        else:
            urlKeys = {}
            for pageData in data["response"]:
                target_field = "content_bz2" if "content_bz2" in pageData and pageData[
                    "content_bz2"] is not None else "content_raw_bz2"
                if target_field in pageData:
                    b64decoded = base64.b64decode(pageData[target_field][2:])
                    decompressed = bz2.decompress(b64decoded)
                    if target_field != "content_bz2":
                        print("we could not parse url %s into %s" % (dbNormalizeURL(pageData["urlTuple"]), output))
                        pageData["content"] = decompressed
                    else:
                        pageData["content"] = pickle.loads(decompressed)
                    del pageData[target_field]
                    urlKeys[pageData["urlKey"]] = pageData
                else:
                    print("there was a problem processing URL %s" % pageData["url"])

            return {urlItem: urlKeys.get(dbNormalizeURL(urlItem), {"url": urlItem, "content": None, "error": True})
                    for urlItem in urlList}
