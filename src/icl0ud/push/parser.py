import inspect
from struct import unpack
from StringIO import StringIO


from icl0ud.push import messages


# TODO rename parser to a more appropriate description
# TODO merge this with messages? - should be implemented analogue to marshalling
class APSParser(object):
    MESSAGE_TYPES = {
        0x07: 'Client Hello',
        0x08: 'Server Hello',
        0x09: 'Push-enabled Topics',
        0x0a: "Push Notification",
        0x0b: 'Push Notification Confirmation',
        0x0c: 'Keep-alive',
        0x0d: 'Keep-alive Response',
    }

    def __init__(self):
        self._typeCache = None

    def isMessageComplete(self, data):
        # print 'isMessageComplete: data: %s' % data.encode('hex')
        if len(data) < 5:
            return False

        messageLength = self.messageLength(data)
        dataLength = len(data)

        if dataLength >= messageLength:
            return True
        return False

    def messageLength(self, data):
        return unpack('!L', data[1:5])[0] + 5

    def messageClassForType(self, type_):
        if not self._typeCache:
            self._typeCache = dict([(cls.type, cls)
                                    for name, cls in inspect.getmembers(messages)
                                    if inspect.isclass(cls)
                                    and issubclass(cls, messages.APSMessage)
                                    and cls.type])
        return self._typeCache.get(type_, messages.APSMessage)

    # TODO decide whether to move this to APSMessage
    # - messages also must be marshalled
    def parseMessage(self, data):
        length = self.messageLength(data)
        stream = StringIO(data[0:length])
        messageType = ord(stream.read(1))
        _ = stream.read(4)  # skip length

        message = self.messageClassForType(messageType)(messageType)
        while stream.tell() < length:
            message.addField(*self.parseField(stream))
        message.parsingFinished()

        return (message, length)

    def parseField(self, stream):
        type_ = ord(stream.read(1))
        length = unpack('!H', stream.read(2))[0]
        return (type_, stream.read(length))
