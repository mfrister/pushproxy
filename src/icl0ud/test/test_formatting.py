import unittest
from copy import deepcopy

import biplist

from icl0ud.push import messages
from icl0ud.test.sample_messages import NOTIFICATION_DICT


class TestMessages(unittest.TestCase):
    def setUp(self):
        self.dict = deepcopy(NOTIFICATION_DICT)

    def test_notification_with_json_payload(self):
        notification = messages.APSNotification(**self.dict)
        formatted = str(notification)
        self.assertEquals(formatted,
                            '''APSNotification com.apple.mediastream.subscription.push
                                   timestamp: 2011-10-29 15:52:20.335509 expiry: 2011-10-30 15:52:20
                                   messageId: deadbeef                   storageFlags: 00
                                   unknown9:  None                       payload decoded (json)
                                   {u'fake': u'payload'}''')

    def test_notification_with_biplist_payload(self):
        imessage_hash = 'e4e6d952954168d0a5db02dbaf27cc35fc18d159'
        self.dict['topic'] = imessage_hash.decode('hex')
        self.dict['payload'] = biplist.writePlistToString({'int': 160})

        notification = messages.APSNotification(**self.dict)
        notification.parsingFinished()
        formatted = str(notification)
        self.assertEquals(formatted,
                            '''APSNotification com.apple.madrid
                                   timestamp: 2011-10-29 15:52:20.335509 expiry: 2011-10-30 15:52:20
                                   messageId: deadbeef                   storageFlags: 00
                                   unknown9:  None                       payload decoded (biplist)
                                   {'int': 160}''')

    def test_notification_with_unknown_payload_and_topic(self):
        self.dict['payload'] = '\x12\x34\x56\x78some payload'
        self.dict['topic'] = '\x12\x34\x56\x78some topic'
        notification = messages.APSNotification(**self.dict)
        formatted = str(notification)
        self.assertEquals(formatted,
                                """APSNotification 12345678736f6d6520746f706963
                                   timestamp: 2011-10-29 15:52:20.335509 expiry: 2011-10-30 15:52:20
                                   messageId: deadbeef                   storageFlags: 00
                                   unknown9:  None                       
                                   '\\x124Vxsome payload'""")

    def test_notification_with_missing_fields(self):
        self.dict['topic'] = None
        self.dict['messageId'] = None
        self.dict['storageFlags'] = None
        self.dict['timestamp'] = None
        self.dict['expires'] = None
        notification = messages.APSNotification(**self.dict)
        notification.parsingFinished()
        formatted = str(notification)
        self.assertEquals(formatted, '''APSNotification <no topic>
                                   timestamp: <none>                     expiry: <none>
                                   messageId: <none>                     storageFlags: <none>
                                   unknown9:  None                       payload decoded (json)
                                   {u'fake': u'payload'}''')
