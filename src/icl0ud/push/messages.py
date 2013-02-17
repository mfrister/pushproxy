import json
import time
from collections import namedtuple
from datetime import datetime, timedelta
from pprint import pformat
from struct import pack, unpack
from StringIO import StringIO

import biplist
from twisted.python import log

from topics import topicForHash


FIELD_INDENTATION = ' ' * 35
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT_MICROSECOND = DATE_FORMAT + '.%f'


FieldT = namedtuple('Field', 'name type')
def Field(name, typ=None):
    return FieldT(name, typ)


def indentLines(string):
    return '\n'.join(map(lambda s: FIELD_INDENTATION + s, string.split('\n')))


class APSMessage(object):
    type = None
    knownValues = {}
    fieldMapping = {}

    def __init__(self, type_=None, source=None, **kwargs):
        if type_ is None and self.type is None:
            raise Exception("APSMessage without type created. " +
                            "Either use subclass or type_ argument.")
        if type_ is not None:
            self.type = type_
        self.fields = []
        self.source = source
        self.rawData = None
        for fieldType, fieldInfo in self.fieldMapping.iteritems():
            value = kwargs.get(fieldInfo.name, None)
            setattr(self, fieldInfo.name, value)
            setattr(self, fieldInfo.name + '_fieldInfo', fieldInfo)

    def __str__(self):
        return self.__repr__()

    def __repr__(self, fields=None):
        # TODO implement version that can be passed to eval
        if not fields:
            if self.fieldMapping:
                fields = self.fieldsAsDict()
            else:
                fields = self.fields

        return '<%s type: %x fields: \n%s>' % \
               (self.__class__.__name__,
                self.type,
                pformat(fields, indent=4))

    def addField(self, type_, content):
        self.fields.append((type_, content))
        if type_ in self.fieldMapping:
            fieldInfo = self.fieldMapping[type_]
            if fieldInfo.type:
                content = self.unmarshalType(fieldInfo.type, content)
                setattr(self, fieldInfo.name + '_marshalled', content)
            setattr(self, fieldInfo.name, content)
        self.checkKnownValues(type_, content)

    def unmarshalType(self, typ, content):
        if typ == 'datetime64':
            integer = unpack('!q', content)[0]
            base = datetime.fromtimestamp(int(integer / 1e9))
            # This reduces accuracy from nanoseconds to microseconds
            microseconds = timedelta(microseconds=(integer % 1e9) / 1000)
            return base + microseconds
        elif typ == 'datetime32':
            return datetime.fromtimestamp(unpack('!l', content)[0])
        elif typ == 'hex':
            return content
        else:
            print 'Warning: {}: Unknown type: {}'.format(
                                                    self.__class__.__name__,
                                                    typ)
            return content

    def parsingFinished(self):
        pass

    def fieldsAsDict(self):
        return dict([(fieldInfo.name, getattr(self, fieldInfo.name))
                     for fieldType, fieldInfo
                     in self.fieldMapping.iteritems()])

    def checkKnownValues(self, type_, value):
        """
        Check whether a field has an unknown value.

        For reverse engineering purposes.
        """
        if not type_ in self.knownValues:
            if type_ in self.fieldMapping:
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
        for type_, fieldInfo in self.fieldMapping.iteritems():
            fieldValue = getattr(self, fieldInfo.name)
            if fieldValue is None:  # ignore fields set to None
                continue
            if not fieldInfo.type or fieldInfo.type in ('str', 'hex'):
                content = fieldValue
            elif fieldInfo.type in('datetime32', 'datetime64'):
                if type(fieldValue) == str:
                    content = fieldValue
                elif fieldInfo.type == 'datetime32':
                    content = pack('!I', int(time.mktime(fieldValue.timetuple())))
                elif fieldInfo.type == 'datetime64':
                    content = pack('!Q', int(time.mktime(fieldValue.timetuple()))
                                         * 1e9 + fieldValue.microsecond * 1000)
            fieldLength = len(content)
            marshalledFields.append(chr(type_) +
                                    pack('!H', fieldLength) +
                                    content)
            length += fieldLength + 3

        return chr(self.type) + pack('!I', length) + ''.join(marshalledFields)

    def fieldInfo(self, name):
        return getattr(self, name + '_fieldInfo')

    FIELD_FORMATTERS = {
        'datetime32': lambda v: v.strftime(DATE_FORMAT),
        'datetime64': lambda v: v.strftime(DATE_FORMAT_MICROSECOND),
        'hex': lambda v: v.encode('hex'),
    }

    def formatField(self, name):
        field = self.fieldInfo(name)
        value = getattr(self, name)
        if value is None:
            return '<none>'
        formatter = self.FIELD_FORMATTERS.get(field.type, lambda v: repr(v))
        return formatter(value)


class APSConnectBase(APSMessage):
    """Base class for APSConnect and APSConnectResponse

    Used by pushtoken_handler to filter messages which define push tokens
    for a connection.
    """
    pass


class APSConnect(APSConnectBase):
    type = 0x07
    fieldMapping = {
        1: Field('pushToken', 'hex'),
        2: Field('state', 'hex'),
        5: Field('presenceFlags', 'hex'),
    }
    knownValues = {
        2: ('\x01', '\x02'),
        5: ('\x00\x00\x00\x01', '\x00\x00\x00\x02'),
    }

    def __str__(self):
        s = '{cls} presenceFlags: {presenceFlags} state: {state}'.format(
                cls=self.__class__.__name__,
                presenceFlags=self.formatField('presenceFlags'),
                state=self.formatField('state'))
        if self.pushToken is not None:
            s += '\n' + FIELD_INDENTATION + 'push token: ' + \
                      self.formatField('pushToken')
        return s


class APSConnectResponse(APSConnectBase):
    type = 0x08
    fieldMapping = {
        1: Field('connectedResponse', 'hex'),
        2: Field('serverMetadata'),
        3: Field('pushToken', 'hex'),  # TODO rename to token
        4: Field('messageSize'),
        5: Field('unknown5', 'hex'),
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

    def __str__(self):
        messageSize = str(unpack('!H', self.messageSize)[0]) \
                      if self.messageSize is not None \
                      else '<none>'
        string = '%s %s messageSize: %s unknown5: %s' % (
                    self.__class__.__name__,
                    self.formatField('connectedResponse'),
                    messageSize,
                    self.formatField('unknown5'))
        if self.pushToken is not None:
            string += '\n' + FIELD_INDENTATION + 'push token: ' + \
                      self.formatField('pushToken')
        if self.serverMetadata is not None:
            string += '\nserver metadata: ' + self.formatField('serverMetadata')
        return string


class APSTopics(APSMessage):
    type = 0x09
    fieldMapping = {
        1: Field('pushToken', 'hex'),
        2: Field('enabledTopics'),
        3: Field('disabledTopics'),
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

    def __str__(self):
        return ('%s for token %s\n' % (self.__class__.__name__,
                                       self.formatField('pushToken')) +
                self.formatTopics(self.enabledTopics, 'enabled topics: ') +
                '\n' +
                self.formatTopics(self.disabledTopics, 'disabled topics:'))

    def formatTopics(self, topicHashes, prefix):
        topics = [topicForHash(hash) for hash in topicHashes]
        string = prefix + ', '.join(topics)
        if len(string) <= 80:
            return FIELD_INDENTATION + string
        string = FIELD_INDENTATION + prefix + '\n'
        for topic in topics:
            string += FIELD_INDENTATION + '  ' + topic + '\n'
        return string[:-1]  # remove last \n


class APSNotification(APSMessage):
    type = 0x0a
    fieldMapping = {
        1: Field('recipientPushToken'),
        2: Field('topic'),  # TODO rename to topicHash
        3: Field('payload'),
        4: Field('messageId', 'hex'),
        5: Field('expires', 'datetime32'),  # TODO rename to expiry
        6: Field('timestamp', 'datetime64'),
        7: Field('storageFlags', 'hex'),
          # seems to indicate whether the server has additional messages
          # stored
          # flags:  0x01: fromStorage
          #         0x02: lastMessageFromStorage
        9: Field('unknown9'),  # ignored
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

    def __str__(self):
        return ('{name} {topic}\n' +
                '{ind}timestamp: {timestamp:<26} expiry: {expiry}\n' +
                '{ind}messageId: {messageId:<26} storageFlags: {storageFlags}\n' +
                '{ind}unknown9:  {unknown9!r:<26} {payload}').format(
                    name=self.__class__.__name__,
                    topic=topicForHash(self.topic) if self.topic else '<no topic>',
                    timestamp=self.formatField('timestamp'),
                    expiry=self.formatField('expires'),
                    messageId=self.formatField('messageId'),
                    storageFlags=self.formatField('storageFlags'),
                    unknown9=self.unknown9,
                    payload=self.formatPayload(),
                    ind=FIELD_INDENTATION)

    def formatPayload(self):
        if self.biplist:
            return 'payload decoded (biplist)\n' + \
                   indentLines(pformat(self.biplist))
        try:
            payload = 'payload decoded (json)\n' + \
                      indentLines(pformat(json.loads(self.payload)))
        except ValueError:
            payload = '\n' + FIELD_INDENTATION + repr(self.payload)
        return payload


class APSNotificationResponse(APSMessage):
    type = 0x0b
    fieldMapping = {
        4: Field('messageId', 'hex'),
        8: Field('deliveryStatus', 'hex'),
    }
    knownValues = {
        8: ('\x00',  # 'Message acknowledged by server'
            '\x02',  # error like in ConnectResponse?
            '\x03',  # 'Server rejected message as invalid'
           ),
    }

    def __str__(self):
        return '%s message: %s status: %s' % (
                    self.__class__.__name__,
                    self.formatField('messageId'),
                    self.formatField('deliveryStatus'))


class APSKeepAlive(APSMessage):
    type = 0x0c
    fieldMapping = {
        1: Field('carrier'),
        2: Field('softwareVersion'),
        3: Field('softwareBuild'),
        4: Field('hardwareVersion'),
        5: Field('keepAliveInterval'),  # in minutes, as string
    }

    def __str__(self):
        return '%s %smin carrier: %s %s/%s/%s' % (self.__class__.__name__,
                                                  self.keepAliveInterval,
                                                  self.carrier,
                                                  self.hardwareVersion,
                                                  self.softwareVersion,
                                                  self.softwareBuild)


class APSKeepAliveResponse(APSMessage):
    type = 0x0d

    def __str__(self):
        return self.__class__.__name__


class APSNoStorage(APSMessage):
    type = 0x0e
    fieldMapping = {
        1: Field('destination', 'hex'),
    }

    def __str__(self):
        return '%s destination: %s' % (self.__class__.__name__,
                                       self.formatField('destination'))


class APSFlush(APSMessage):
    type = 0x0f
    fieldMapping = {
        1: Field('flushWantPadding'),
        2: Field('padding'),
    }

    def __str__(self):
        return '%s flushWantPadding: %d\npadding(%d byte): %s' % (
                self.__class__.__name__,
                unpack('!H', self.flushWantPadding)[0],
                len(self.padding),
                self.padding.encode('hex'))
