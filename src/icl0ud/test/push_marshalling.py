import unittest
from datetime import datetime

from icl0ud.push import messages
from icl0ud.push.parser import APSParser


class TestMessages(unittest.TestCase):
    def setUp(self):
        self.marshalledMessage = \
                          "\n\x00\x00\x00T\x01\x00\tfakeToken\x02\x00\x14E" +\
                          "\xd4\xa8\xf8\xd8?\xdc{\xa9b3\x01\x8f\xe1\xaaG_" + \
                          "\xbc\xcdn\x03\x00\x11{fake: 'payload'}\x04\x00" + \
                          "\x04\xde\xad\xbe\xef\x05\x00\x04N\xadd\xa4\x06" + \
                          "\x00\x08\x12Q6\xbaf\t\xc8\x00\x07\x00\x01\x00"
        self.messageFields = {
            'recipientPushToken': 'fakeToken',
            'topic': '45d4a8f8d83fdc7ba96233018fe1aa475fbccd6e'.decode('hex'),
            'payload': "{fake: 'payload'}",
            'messageId': '\xde\xad\xbe\xef',
            'expires': datetime(2011, 10, 30, 15, 52, 20, 335509),
            'timestamp': datetime(2011, 10, 29, 15, 52, 20, 335509),
            'storageFlags': '\x00',
        }

    def test_marshal_notification(self):
        notification = messages.APSNotification(**self.messageFields)
        marshalled = notification.marshal()

        self.assertEquals(self.marshalledMessage, marshalled)

    def test_parse_notification(self):
        parser = APSParser()
        message, rest = parser.parseMessage(self.marshalledMessage)

        fields = self.messageFields
        self.assertEquals(message.recipientPushToken,
                          fields['recipientPushToken'])
        self.assertEquals(message.topic,
                          fields['topic'])
        self.assertEquals(message.payload,
                          fields['payload'])
        self.assertEquals(message.messageId,
                          fields['messageId'])
        self.assertEquals(message.expires,
                          'N\xadd\xa4')
        self.assertEquals(message.timestamp,
                          '\x12Q6\xbaf\t\xc8\x00')
        self.assertEquals(message.storageFlags,
                          fields['storageFlags'])
