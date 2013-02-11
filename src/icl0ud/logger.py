import sys

from twisted.python import log, logfile, util


class PushLogObserver(log.FileLogObserver):
    """Logger that doesn't output system context"""
    def emit(self, eventDict):
        text = log.textFromEventDict(eventDict)
        if text is None:
            text = '<no text>'

        timeStr = self.formatTime(eventDict['time'])
        fmtDict = {'time': timeStr, 'text': text}
        output = log._safeFormat('%(time)s %(text)s\n', fmtDict)
        util.untilConcludes(self.write, output)
        util.untilConcludes(self.flush)


def stdoutLogger():
    # catch sys.stdout before twisted overwrites it
    return PushLogObserver(sys.stdout).emit


def fileLogger():
    logFile = logfile.LogFile.fromFullPath('data/push.log',
                                           rotateLength=10000000)  # 10 MB
    return PushLogObserver(logFile).emit
