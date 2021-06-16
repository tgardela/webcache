import json
from webcacheclient import WebCacheClient


def play_get_request():
    client = WebCacheClient()

    urlList = [f"https://nominatim.openstreetmap.org/search/Credit Suisse,{zipcode},Switzerland?osm_type=N&format=json"
               for zipcode in range(2095, 2099)]
    ret = client.fetchURLs(urlList, category="OSM-geocoding", output="json")
    print(ret)


def play_get_request():
    import sys
    client = WebCacheClient()

    urlList = [f"https://nominatim.openstreetmap.org/search/Bank,{zipcode},Switzerland?osm_type=N&format=json"
               for zipcode in range(2095, 2199)]
    ret = client.fetchURLs(urlList, category="OSM-geocoding", output="json")
    print(ret)


def play_get_request_without_proxies():
    client = WebCacheClient()

    urlList = ["http://localhost:7070/search/Switzerland?osm_type=N&format=json",
               "http://localhost:7070/search/Germany?osm_type=N&format=json"]
    ret = client.fetchURLs(urlList, category="OSM-geocoding", output="json")
    print(ret)


def play_post_request():
    client = WebCacheClient()

    urlList = [f"https://search.wdoms.org?sSchoolName={medschool}&iPageNumber=1" for medschool in
               ['Basel', 'Zürich', 'London']]
    ret = client.fetchURLs(urlList, category="medschool", output="xml", method="POST")
    print(ret)


def play_post_data_request():
    client = WebCacheClient()

    urlList = [("https://search.wdoms.org", json.dumps({'sSchoolName': medschool, 'iPageNumber': 1})) for medschool in
               ['Basel', 'Zürich', 'London']]
    ret = client.fetchURLs(urlList, category="medschool", output="xml", method="POST")
    print(ret)


def getProxy():
    client = WebCacheClient()
    print(client.getProxyList(10000))


if __name__ == '__main__':
    # play_post_request()
    # play_post_data_request()
    play_get_request()
    #play_get_request_without_proxies()
    # getProxy()
