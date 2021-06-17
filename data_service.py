#!flask/bin/python

import json
import traceback

from flask import Flask, jsonify, abort, make_response, request
import pymongo

from helpers import getData, getFlaskIP, getMongoLocation, isValidURL
from models.DBProxyHandler import DBProxyHandler


app = Flask(__name__)


@app.route("/fetch/<int:maxAgeDays>/<string:category>/<string:output>/<string:method>", methods=["POST"])
def fetchURL(maxAgeDays, category, output="html", method="GET"):
    try:
        if output.lower() not in ["xml", "json"]:
            raise ValueError("we only support XML and JSON as output formats for now")

        urls = json.loads(request.form["urls"])
        urls = [urlTuple for urlTuple in urls if isValidURL(urlTuple[0])]

        print("preparing to fetch data for %s urls.." % len(urls))
        theData = {"response": list(getData(
            urls, method, maxAgeDays, category, output)) if len(urls) > 0 else []}
        return make_response(jsonify(**theData))

    except Exception as e:
        print(traceback.format_exc())
        abort(500, e)


@app.route("/proxies/<int:numProxies>", methods=["GET"])
def getProxies(numProxies):
    client = pymongo.MongoClient(getMongoLocation())
    db = client.webdata
    ph = DBProxyHandler(db)
    data = {"response": ph.pick(numProxies)}
    return make_response(jsonify(**data))


@app.errorhandler(500)
def not_found(error):
    return make_response(jsonify({"error": str(error), "traceback": str(error.__traceback__)}))


if __name__ == '__main__':
    client = pymongo.MongoClient(getMongoLocation())
    db = client.webdata
    db.webpages.create_index([('urlKey', pymongo.ASCENDING)], unique=True)
    db.webpages.create_index([('creation_date', pymongo.ASCENDING)])
    client.close()
    url_counter = {}
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    app.run(host=getFlaskIP(), port=9011, debug=True)
