from datetime import datetime
from pprint import pformat
from struct import pack, unpack
from StringIO import StringIO
import time

import biplist
from twisted.python import log


class APSMessage(object):
    type = None
    knownValues = {}
    simpleFieldMapping = {}

    def __init__(self, type_=None, source=None, **kwargs):
        if type_ is None and self.type is None:
            raise Exception("APSMessage without type created. " +
                            "Either use subclass or type_ argument.")
        if type_ is not None:
            self.type = type_
        self.fields = []
        self.source = source
        self.rawData = None
        for fieldType, fieldInfo in self.simpleFieldMapping.iteritems():
            value = kwargs.get(fieldInfo[0], None)
            setattr(self, fieldInfo[0], value)

    def __repr__(self, fields=None):
        if not fields:
            if self.simpleFieldMapping:
                fields = self.fieldsAsDict()
            else:
                fields = self.fields

        return '<%s %s type: %x fields: \n%s>' % \
               (self.source,
                self.__class__.__name__,
                self.type,
                pformat(fields, indent=4))

    def addField(self, type_, content):
        self.fields.append((type_, content))
        if type_ in self.simpleFieldMapping:
            fieldInfo = self.simpleFieldMapping[type_]
            setattr(self, fieldInfo[0], content)
        self.checkKnownValues(type_, content)

    def parsingFinished(self):
        pass

    def fieldsAsDict(self):
        return dict([(fieldInfo[0], getattr(self, fieldInfo[0]))
                     for fieldType, fieldInfo
                     in self.simpleFieldMapping.iteritems()])

    def checkKnownValues(self, type_, value):
        """
        Check whether a field has an unknown value.

        For reverse engineering purposes.
        """
        if not type_ in self.knownValues:
            if type_ in self.simpleFieldMapping:
                return
            log.err('%s: unknown field: %x value: %s' %
                    (self.__class__.__name__,
                     type_,
                     value.encode('hex')))
            return
        if not value in self.knownValues[type_]:
            log.err('%s: unknown value for field: %x value %s' % (
                    self.__class__.__name__,
                    type_,
                    value.encode('hex')))

    def marshal(self):
        marshalledFields = []
        length = 0
        for type_, fieldInfo in self.simpleFieldMapping.iteritems():
            fieldValue = getattr(self, fieldInfo[0])
            if fieldValue is None:  # ignore fields set to None
                continue
            if len(fieldInfo) < 2 or fieldInfo[1] == 'str':
                content = fieldValue
            elif fieldInfo[1] in('datetime32', 'datetime64'):
                if type(fieldValue) == str:
                    content = fieldValue
                elif fieldInfo[1] == 'datetime32':
                    content = pack('!I', int(time.mktime(fieldValue.timetuple())))
                elif fieldInfo[1] == 'datetime64':
                    content = pack('!Q', int(time.mktime(fieldValue.timetuple()))
                                         * 10 ** 9)
            fieldLength = len(content)
            marshalledFields.append(chr(type_) +
                                    pack('!H', fieldLength) +
                                    content)
            length += fieldLength + 3

        return chr(self.type) + pack('!I', length) + ''.join(marshalledFields)


class APSConnectBase(APSMessage):
    def __repr__(self):
        fields = self.fieldsAsDict()
        if self.pushToken:
            fields['pushToken'] = self.pushToken.encode('hex')
        return super(APSConnectBase, self).__repr__(fields)


class APSConnect(APSConnectBase):
    type = 0x07
    simpleFieldMapping = {
        1: ('pushToken',),
        2: ('state',),
        5: ('presenceFlags',),
    }
    knownValues = {
        2: ('\x01',),
        5: ('\x00\x00\x00\x01', '\x00\x00\x00\x02'),
    }


class APSConnectResponse(APSConnectBase):
    type = 0x08
    simpleFieldMapping = {
        1: ('connectedResponse',),
        2: ('serverMetadata',),
        3: ('pushToken',),  # TODO rename to token
        4: ('messageSize',),
        5: ('unknown5',),
    }
    knownValues = {
        1: ('\x00',  # ok
            '\x02',  # some error, connection closed, immediate reconnect
                     #  - first try client sends push token, second try: no push
                     #    token in client hello - status for invalid push token?
            ),
        4: ('\x10\x00',),
        5: ('\x00\x02',),
    }


class APSTopics(APSMessage):
    type = 0x09
    simpleFieldMapping = {
        1: ('pushToken',),
        2: ('enabledTopics',),
        3: ('disabledTopics',),
    }

    def __init__(self, *args, **kwargs):
        super(APSTopics, self).__init__(*args, **kwargs)
        self.enabledTopics = []
        self.disabledTopics = []

    def addField(self, type_, content):
        if type_ == 2:
            self.enabledTopics.append(content)
        elif type_ == 3:
            self.disabledTopics.append(content)
        else:
            super(APSTopics, self).addField(type_, content)

    def __repr__(self):
        fields = {
            'pushToken': self.pushToken.encode('hex') \
                if self.pushToken else None,
            'enabledTopics': self.hexEncodeStrList(self.enabledTopics),
            'disabledTopics': self.hexEncodeStrList(self.disabledTopics),
        }
        return super(APSTopics, self).__repr__(fields)

    def hexEncodeStrList(self, list_):
        return [str_.encode('hex') for str_ in list_]


class APSNotification(APSMessage):
    type = 0x0a
    simpleFieldMapping = {
        1: ('recipientPushToken',),
        2: ('topic',),  # TODO rename to topicHash
        3: ('payload',),
        4: ('messageId',),
        5: ('expires', 'datetime32'),  # TODO rename to expiry
        6: ('timestamp', 'datetime64'),
        7: ('storageFlags',),
          # seems to indicate whether the server has additional messages
          # stored
          # flags:  0x01: fromStorage
          #         0x02: lastMessageFromStorage
        9: ('unknown9',),  # ignored
    }
    topicDescriptions = {
        '45d4a8f8d83fdc7ba96233018fe1aa475fbccd6e': 'PhotoStream',
        '5a5fc3a1fea1dfe3770aab71bc46d0aa8a4dad41': 'Ubiquity',
        '79afbbadc8f8142d144202ed12106d5cd3f88f1a': 'Find My iPhone',
        'e4e6d952954168d0a5db02dbaf27cc35fc18d159': 'iMessage',
        'e85619abd42029c7481a7ac19092bb4690cbee76': 'FaceTime',
    }

    def __init__(self, *args, **kwargs):
        super(APSNotification, self).__init__(*args, **kwargs)
        self.biplist = None

    def parsingFinished(self):
        # decode iMessage biplist payload
        iMessageTopic = 'e4e6d952954168d0a5db02dbaf27cc35fc18d159' \
                         .decode('hex')
        if self.topic == iMessageTopic \
            or self.recipientPushToken == iMessageTopic:

            self.biplist = biplist.readPlist(StringIO(self.payload))

    def __repr__(self):
        fields = self.fieldsAsDict()
        if self.biplist:
            fields['biplist'] = self.biplist
            del fields['payload']
        fieldsToHexEncode = ('topic', 'recipientPushToken')
        for fieldName in fieldsToHexEncode:
            if fields[fieldName]:
                fields[fieldName] = fields[fieldName].encode('hex')

        if self.topic is not None:
            fields['topic_description'] = self.topicDescriptions.get(
                                          self.topic.encode('hex'), None)
        if self.expires is not None and type(self.expires) == str:
            fields['expires'] = datetime.fromtimestamp(unpack('!l', self.expires)[0])
        if self.timestamp is not None and type(self.timestamp) == str:
            seconds = float(unpack('!q', self.timestamp)[0]) / 1000000000
            fields['timestamp'] = datetime.fromtimestamp(seconds)

        return super(APSNotification, self).__repr__(fields)


class APSNotificationResponse(APSMessage):
    type = 0x0b
    simpleFieldMapping = {
        4: ('messageId',),
        8: ('deliveryStatus',),
    }
    knownValues = {
        8: ('\x00',  # 'Message acknowledged by server'
            '\x02',  # error like in ConnectResponse?
            '\x03',  # 'Server rejected message as invalid'
           ),
    }


class APSKeepAlive(APSMessage):
    type = 0x0c
    simpleFieldMapping = {
        1: ('carrier',),
        2: ('softwareVersion',),
        3: ('softwareBuild',),
        4: ('hardwareVersion',),
        5: ('keepAliveInterval',),  # in minutes, as string
    }


class APSKeepAliveResponse(APSMessage):
    type = 0x0d


class APSNoStorage(APSMessage):
    type = 0x0e
    simpleFieldMapping = {
        1: ('destination',),
    }


class APSFlush(APSMessage):
    type = 0x0f
    simpleFieldMapping = {
        1: ('flushWantPadding',),
        2: ('padding',),
    }
