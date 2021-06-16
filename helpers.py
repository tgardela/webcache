import base64
from bs4 import BeautifulSoup
import bz2
import datetime
import json
import multiprocessing
import os
import pickle
import re
import requests
from requests.exceptions import (
    ProxyError,
    ConnectTimeout,
    SSLError,
    ConnectionError,
    ChunkedEncodingError,
    ReadTimeout
)
from typing import Union

import furl
import pymongo

from exceptions import CaptchaError, SkipURL
from models.DBProxyHandler import DBProxyHandler


def dbNormalizeURL(urlItem):
    theUrl, theData = (urlItem, {}) if type(urlItem) is str else (urlItem[0], json.loads(urlItem[1]))
    try:
        lowerLinkFurl = furl.furl(
            theUrl.lower().strip().replace("https://", "http://"))  # consider http and https as EQUAL for the key
        lowerLinkFurl.path.normalize()
        lowerLinkFurl.query.params = sorted(
            [(par, lowerLinkFurl.query.params[par]) for par in lowerLinkFurl.query.params],
            key=lambda item: item[0])
        lowerLinkFurl.path = "%s/" % lowerLinkFurl.path if not str(lowerLinkFurl.path).endswith(
            "/") else lowerLinkFurl.path
        lowerLink = lowerLinkFurl.url

        if theData:
            dataJSON = json.dumps(theData, sort_keys=True).lower()
            lowerLink = f"{lowerLink}_{dataJSON}"

        return lowerLink
    except:
        print("COULD NOT DB NORM URL %s" % theUrl)
        return None


def getData(urlList: list, method: str, maxAgeDays: int, category, output="xml"):
    if method.upper() not in ['GET', 'POST']:
        raise ValueError("only GET/POST supported")

    urlData = {dbNormalizeURL(urlTuple): {"urlTuple": urlTuple, "urlKey": dbNormalizeURL(urlTuple)} for urlTuple in
               urlList}

    db = pymongo.MongoClient(getMongoLocation()).webdata
    existing = {data["urlKey"]: data for data in
                db.webpages.find({"urlKey": {"$in": list(urlData.keys())}, "format": output,
                                  "creation_date": {"$gt": datetime.now() - datetime.timedelta(days=maxAgeDays)}})}
    urlData.update(existing)

    # for those where we do not have data -> obtain
    urlKeysToObtain = [urlKey for urlKey in urlData if "format" not in urlData[urlKey]]
    print("found %s entries already and will need to obtain an additional %s. Total Unique urls: %s" % (
        len(existing), len(urlKeysToObtain), len(urlData)))
    if len(urlKeysToObtain) > 0:
        global url_counter
        url_counter = {urlKey: 0 for urlKey in urlKeysToObtain}
        chunkLen = int(len(urlKeysToObtain) / os.cpu_count())
        chunkLen = chunkLen if chunkLen != 0 else 1
        processes = [multiprocessing.Process(target=processURLChunk, args=(
            urlKeysToObtain[x:x + chunkLen], urlData, method, output, category, maxAgeDays)) for x in
                     range(0, len(urlKeysToObtain), chunkLen)]
        for proc in processes:
            proc.start()

        for proc in processes:
            proc.join()
        client = pymongo.MongoClient(getMongoLocation())
        db = client.webdata
        remainingData = {data["urlKey"]: data for data in db.webpages.find(
            {"urlKey": {"$in": list(urlData.keys())}, "format": output,
             "creation_date": {"$gt": datetime.now() - datetime.timedelta(days=maxAgeDays)}})}
        client.close()
        urlData.update(remainingData)

    print("finished obtaining data, encoding everything and returning it.")

    for data in urlData:
        targetField = "content_bz2" if "content_bz2" in urlData[data] and urlData[data][
            "content_bz2"] is not None else "content_raw_bz2"
        if targetField in urlData[data]:
            urlData[data][targetField] = str(base64.b64encode(urlData[data][targetField]))
        else:
            urlData[data]["error"] = "could not obtain address!"
            urlData[data]["content_raw_bz2"] = ""
        if "_id" in urlData[data]:
            del urlData[data]["_id"]
    return urlData.values()


def getFlaskIP() -> str:
    return "127.0.0.1"
    # return "10.5.133.201"


def getMaxTimeForUrl() -> int:
    return 20


def getMongoLocation() -> str:
    return "127.0.0.1"


def has_captcha(response: Union[json.JSONEncoder, BeautifulSoup]) -> bool:
    recaptcha_url = re.compile('https?://www.google.com/recaptcha/api.*')
    if isinstance(response, json.JSONEncoder):
        pass
    elif isinstance(response, BeautifulSoup):
        script_tags = response.find_all('script')
        for script in script_tags:
            try:
                if recaptcha_url.match(script['src']):
                    return True
            except KeyError:
                pass
        iframe_tags = response.find_all('iframe')
        for iframe in iframe_tags:
            try:
                if recaptcha_url.match(iframe['src']):
                    return True
            except KeyError:
                pass
    return False


def isValidURL(url):
    return type(url) == str and len(url.strip()) > 0 and url.startswith("http")


def processURLChunk(chunk, urlData, method, output, category, maxAgeDays):
    print("process started for %s URL's in category %s" % (len(chunk), category))
    if len(chunk) < 1: return
    with multiprocessing.pool.ThreadPool(min(100, len(chunk))) as thread_pool:
        thread_pool.starmap(tryNTimesToGetPage,
                            [(urlKey, urlData[urlKey]["urlTuple"], method, output, category, maxAgeDays) for urlKey in
                             chunk])
        print("process finished %s URL's in category %s" % (len(chunk), category))


def tryNTimesToGetPage(urlKey: str, urlTuple: tuple, method: str, output: str, category: str, maxAgeDays, tries=0,
                       multiprocessed=False):
    with pymongo.MongoClient(getMongoLocation()) as client:
        db = client.webdata
        finished = {data["urlKey"]: data for data in db.webpages.find({"urlKey": {"$in": [urlKey]}, "format": output,
                                                                       "creation_date": {
                                                                           "$gt": datetime.now() - datetime.timedelta(
                                                                               days=maxAgeDays)}})}
    if finished:
        return
    print("attempt %s to get URL %s" % (tries, dbNormalizeURL(urlTuple)))
    if url_counter[urlKey] >= getMaxTimeForUrl():
        print("I'm giving up fetching URL %s" % dbNormalizeURL(urlTuple))
        return
    with pymongo.MongoClient(getMongoLocation()) as client:
        db = client.webdata
        ph = DBProxyHandler(db)
        proxy = ph.pick()
        try:
            result = obtainPage(urlTuple, method, output, proxy)
            result["category"] = category
            ph.feedback(proxy, 1)
            updateDBEntry(result, urlTuple)
            return
        except (ProxyError,
                ConnectTimeout,
                SSLError,
                ConnectionError,
                ReadTimeout,
                ChunkedEncodingError,
                CaptchaError) as e:
            ph.feedback(proxy, -1)
            if not multiprocessed:
                with multiprocessing.pool.ThreadPool(5) as pool:
                    new_queries = []
                    for i in range(1, 6):
                        url_counter[urlKey] = url_counter[urlKey] + 1
                        new_queries.append(
                            (urlKey, urlTuple, method, output, category, maxAgeDays, url_counter[urlKey], True))
                    url_counter[urlKey] = url_counter[urlKey] + 5
                    pool.starmap(tryNTimesToGetPage, new_queries)
            else:
                url_counter[urlKey] = url_counter[urlKey] + 1
                tryNTimesToGetPage(urlKey, urlTuple, method, output, category, maxAgeDays, url_counter[urlKey], True)
        except:
            print("encountered exception on url %s: %s" % (dbNormalizeURL(urlTuple), traceback.format_exc()))
            return


def timeDiffToNow(previousTime):
    diff = (datetime.datetime.now() - previousTime)
    return diff.microseconds + diff.seconds*10**6


def updateDBEntry(result, urlTuple, nTries=2):
    client = pymongo.MongoClient(getMongoLocation())
    db = client.webdata
    if nTries < 0:
        return None
    try:
        db.webpages.replace_one({"urlKey": dbNormalizeURL(urlTuple)}, result, upsert=True)
    except pymongo.errors.AutoReconnect:
        print("pymongo error: could not autoreconnect")
        updateDBEntry(result, nTries - 1)
    client.close()


def obtainPage(urlTuple: tuple, method: str, output: str, proxy: str):
    url, dataJson = urlTuple[0], urlTuple[1]
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        'User-Agent': "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_7;en-us) AppleWebKit/530.17 (KHTML, like Gecko) Version/4.0 Safari/530.17"
    }
    downloadStartTime = datetime.now()
    requests.packages.urllib3.disable_warnings()

    with requests.request(method, url, data=json.loads(dataJson), headers=headers, verify=False, stream=True,
                          proxies={"https": proxy, "http": proxy}, timeout=60) as req:
        maxsize = 5e6  # max size = 5MB. Will stop afterwards
        data = b''
        encounteredSizeLimit = False
        parsedData = None
        try:
            for chunk in req.iter_content(2048):
                data += chunk
                if len(data) > maxsize:
                    raise SkipURL("too much data. I'm limited to %s bytes" % maxsize)
            try:
                interpreter = json.loads(data.decode()) if output.lower() == "json" else BeautifulSoup(data, "lxml")
                if has_captcha(interpreter):
                    raise CaptchaError('Captcha response detected.')
                parsedData = bz2.compress(pickle.dumps(interpreter))
            except:
                pass  # if we cannot parse the data..
        except SkipURL:
            encounteredSizeLimit = True
            pass

        toReturn = {"download_duration_ms": timeDiffToNow(downloadStartTime), "content_bz2": parsedData,
                    "size": len(data),
                    "urlTuple": urlTuple, "format": output,
                    "urlKey": dbNormalizeURL(urlTuple), "creation_date": datetime.now()}
        if encounteredSizeLimit:
            toReturn["cancelled"] = "size limit"
        if parsedData is None:
            toReturn["cancelled"] = "parsing error"
            toReturn["content_raw_bz2"] = bz2.compress(data)

        return toReturn

