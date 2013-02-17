from datetime import datetime

NOTIFICATION_MARSHALLED = (
                  '\n\x00\x00\x00V\x01\x00\tfakeToken\x02\x00\x14E' +
                  '\xd4\xa8\xf8\xd8?\xdc{\xa9b3\x01\x8f\xe1\xaaG_\xbc' +
                  '\xcdn\x03\x00\x13{"fake": "payload"}\x04\x00\x04\xde' +
                  '\xad\xbe\xef\x05\x00\x04N\xadd\xa4\x06\x00\x08\x12' +
                  'Q6\xbaz\t>\x00\x07\x00\x01\x00')

NOTIFICATION_DICT = {
    'recipientPushToken': 'fakeToken',
    'topic': '45d4a8f8d83fdc7ba96233018fe1aa475fbccd6e'.decode('hex'),
    'payload': '{"fake": "payload"}',
    'messageId': '\xde\xad\xbe\xef',
    'expires': datetime(2011, 10, 30, 15, 52, 20),
    'timestamp': datetime(2011, 10, 29, 15, 52, 20, 335509),
    'storageFlags': '\x00',
}
