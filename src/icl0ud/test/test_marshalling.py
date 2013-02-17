from twisted.trial import unittest

from icl0ud.push import messages
from icl0ud.push.parser import APSParser
from icl0ud.test.sample_messages import (NOTIFICATION_MARSHALLED,
                                              NOTIFICATION_DICT)


class TestMessages(unittest.TestCase):
    def test_marshal_notification(self):
        notification = messages.APSNotification(**NOTIFICATION_DICT)
        marshalled = notification.marshal()

        self.assertEquals(NOTIFICATION_MARSHALLED, marshalled)

    def test_parse_notification(self):
        parser = APSParser()
        message, rest = parser.parseMessage(NOTIFICATION_MARSHALLED)

        self.assertEquals(message.recipientPushToken,
                          NOTIFICATION_DICT['recipientPushToken'])
        self.assertEquals(message.topic,
                          NOTIFICATION_DICT['topic'])
        self.assertEquals(message.payload,
                          NOTIFICATION_DICT['payload'])
        self.assertEquals(message.messageId,
                          NOTIFICATION_DICT['messageId'])
        self.assertEquals(message.expires,
                          NOTIFICATION_DICT['expires'])
        self.assertEquals(message.timestamp,
                          NOTIFICATION_DICT['timestamp'])
        self.assertEquals(message.storageFlags,
                          NOTIFICATION_DICT['storageFlags'])
