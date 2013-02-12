import traceback

from twisted.python import log

from icl0ud.utils.hexdump import hexdump


class BaseDispatch(object):
    """Message dispatching mix-in"""

    @property
    def handlers(self):
        if not hasattr(self, '_handlers'):
            self._handlers = set()
        return self._handlers

    def addHandlers(self, handlers):
        map(self.addHandler, handlers)

    def addHandler(self, handler):
        self.handlers.add(handler)

    def removeHandlers(self, handlers):
        map(self.removeHandler, handlers)

    def removeHandler(self, handler):
        self.handlers.pop(handler)

    def dispatch(self, source, message):
        forwardMessage = True

        for handler in self.handlers:
            try:
                deviceProtocol = self.getDeviceProtocol()
                result = handler.handle(source, message, deviceProtocol)
                if not result in (True, None):
                    log.msg('BaseDispatch: Skipping message forward ' +
                            'due to %s' % handler.__class__.__name__)
                    forwardMessage = False
            except Exception:
                log.err(handler.__class__.__name__ + ': ' + \
                        traceback.format_exc())
                log.err(source)
                log.err(message)
                forwardMessage = False
        return forwardMessage


class BaseHandler(object):
    def handle(self, source, *args, **kwargs):
        raise NotImplementedError()


class LoggingHandler(BaseHandler):
    sourcePrefixMap = {'server': '<-', 'device': '->'}

    def handle(self, source, msg, deviceProtocol):
        direction = self.sourcePrefixMap[source]
        deviceProtocol.log(direction + ' ' + str(msg))


class HexdumpHandler(LoggingHandler):
    def __init__(self, fd, *args, **kwargs):
        self.fd = fd
        super(HexdumpHandler, self).__init__()

    def handle(self, source, msg, *args, **kwargs):
        self.fd.write(self.sourcePrefixMap[source] + '\n')
        hexdump(msg.rawData, write_to_fd=self.fd)
        self.fd.flush()
