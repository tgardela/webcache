# webcache_refactoring_template

One of the modules that are frequently used across our system is called *webcache*. It's a microservice, that abstracts the handling of *unsafe/unreliable anonymous public proxies* to obtain content for URL's. It's current functionalities are:
* client that is able to connect to micro service, pass thousands of URL's that should be obtained by webcache-microservice at once, tell it how to parse the URL's and do some basic sanity checking with it. Then, once results from the service for all the passed URL's come in, interpret them and return them. (See `webcacheclient.py` for client code and `test_webcache.py` for integration tests to see how it is being used)
* the webcache service `data_service.py` includes a Flask endpoint to receive page-requests (of hundreds or thousands of URL's that are to be obtained concurrently). It then proceeds to obtain these URL's in parallel using the *unreliable proxies*. If a proxy dies / timeouts, it tries to get the same page again using another proxy - up to 20 times. As soon as the obtaining of an URL was successful, it is stored in MongoDB (such that it can return immediately next time - provided the cache-retainment duration is not exceeded). Then, the URL's are parsed using the format expected by the client (currently, lxml and json), compressed and returned to the client. 
* in the webcache service, on-proxy-failure, multiple new proxies try to obtain the same URL again. This is called speculative execution, and should reduce the waiting time of the client for data

The goals of the webcache are: 
* quickly obtain data for a large set of URL's while distributing requests over many different proxies 
* reliably obtain data for a large set of URL's
* reuse even slow proxies for requesting data (even though we want most requests to go over fast proxies - small proxies should also be used)
* be sure to distinguish between an actual failure of the URL (eg 404) and a failure of an unreliable proxy that you used to get the URL! This can sometimes be tricky
* enable the dev to specify how he wants to obtain these URLs (HTTP headers, GET vs POST, cookies etc). This goal is currently only partially satisfied, and your rewrite should satisfy the full goal
* extensibility

The webcache service has been hacked together under time pressure initially with a very small and simple goal. Since then it grew uglier and uglier with every additional functionality it had to serve. Meanwhile, it's safe to say that it is one of the worst modules of our code base overall. Your task is to refactor or even reimplement the webservice. Take care that: 
* You are allowed to suggest a different method signatures for client/server. When you do so, keep in mind the goal above (*enable the dev to specify how he wants to obtain these URLs (HTTP headers, GET vs POST, cookies etc).*)
* This is mostly an exercise, so feel free to change everything and anything you want. You can also re-implement from scratch if you think that gets the task done better. Take care to adhere to the goals. 
* Think of this as a mini showcase of your working mode. For example: if you care about architecture & code quality, invest your time there. If you care about unit tests, invest your time there. 
* We generally follow the clean-code principle: extract methods for hard-to-understand code sections with proper names, and use variables with good names extensively. 
  Your code should be readable like a book - also by someone who is not a Python coder (but who has coding experience).


# You have 2h
* Please stop after 2h. You probably won't complete the whole task in 2h. 
But we will be able to see where your priorities lie and how you managed your limited time. 
* Start by:
  1. Creating a personal repo for this project into your personal gitlab account.
  1. Create a feature branch (in your personal gitlab account).
* Finish by:
  1. Creating a Merge-Request from your personal feature branch, to your personal master branch.    
  1. Create a merge request and share the link to the merge request with us.
