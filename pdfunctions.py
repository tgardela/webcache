import datetime


def timeDiffToNow(previousTime):
    diff = (datetime.datetime.now() - previousTime)
    return diff.microseconds + diff.seconds*10**6
