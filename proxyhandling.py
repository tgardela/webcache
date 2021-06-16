import requests
import re, bs4, math
from joblib import Parallel, delayed
import random
from pymongo import InsertOne, DeleteOne, ReplaceOne
import pymongo


class DBProxyHandler:
    db = None
    proxies = []

    def __init__(self, db):
        self.db = db

    def upload(self, proxyList):
        cleanedList = [item.replace("\n", "") for item in proxyList]
        self.db.proxies.bulk_write(
            [ReplaceOne({"address": item}, {"address": item, "successful_job_completion": 0}, upsert=True) for item in
             cleanedList],
            ordered=False)

    def pick(self, n=1, nTries=3):
        if n < 1:
            raise ValueError("you must at least one proxy")

        if nTries < 3:
            return

        try:
            # strategy: proxys that work well shoul be reused more often. Proxies that didn't work for 45 consecutive requests are dropped
            proxies = list(self.db.proxies.find({"successful_job_completion": {"$gt": -30}}).limit(min(10000, 1000 * n)))
            for proxy in proxies:
                proxy["score"] = random.random() * min(max(proxy["successful_job_completion"], -5), 5)

            chosenProxies = random.choices(population=proxies, weights=[proxy["score"] for proxy in proxies], k=n)

            if len(proxies) == 0:
                raise ValueError("no proxies available!")
            else:
                if n == 1:
                    return dict(chosenProxies[0])["address"]
                else:
                    return [dict(pro)["address"] for pro in chosenProxies]
        except pymongo.errors.AutoReconnect:
            print("pymongo error in proxy.pick: could not autoreconnect")
            self.pick(n, nTries-1)

    def feedback(self, address, counter=1, nTries=3):
        if nTries < 0:
            return

        try:
            proxy = self.db.proxies.find_one({"address": address})
            self.db.proxies.update_one({"address": address}, {
                "$set": {"successful_job_completion": proxy.get("successful_job_completion", 0) if proxy is not None else 0
                                                           + counter}}, upsert=True)  # allow max 15 plus points. if proxy goes offline, max 45 req will drop it
        except pymongo.errors.AutoReconnect:
            print("pymongo error in feedback: could not autoreconnect")
            self.feedback(address, counter, nTries-1)
