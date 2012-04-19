import random
from datetime import datetime, timedelta
from struct import pack

from twisted.python import log
from twisted.spread import pb

from icl0ud.push.dispatch import BaseHandler
from icl0ud.push.messages import APSNotification, APSNotificationResponse

# FIXME rename this module

class PushNotificationSender(BaseHandler, pb.Root):
    def __init__(self, tokenHandler):
        self._tokenHandler = tokenHandler
        self._responseTokens = {}

    def handle(self, source, message, deviceProtocol):
        if not isinstance(message, APSNotificationResponse):
            return True
        if message.responseToken in self._responseTokens:
            log.msg('PushNotificationSender: Found message with ' +
                    'self-issued response token: %s'
                    % repr(message))
            del self._responseTokens[message.responseToken]
            return False
        return True

    def sendMessageToDevice(self, pushToken, message):
        deviceProtocol = self._tokenHandler.deviceProtocolForToken(pushToken)
        data = message.marshal()
        print 'PushNotificationSender: Sending to device: %s' % data.encode('hex')
        deviceProtocol.transport.write(data)

    def generateResponseToken(self):
        token = None
        while token in self._responseTokens or token is None:
            token = pack("!L", random.randint(0, 2**32-1))
        self._responseTokens[token] = True
        return token

    def remote_sendNotification(self, pushToken, topic, payload):
        notification = APSNotification(
            recipientPushToken = pushToken,
            topic = topic,
            payload = payload,
            responseToken = self.generateResponseToken(),
            expires = datetime.now() + timedelta(days=1),
            timestamp = datetime.now(),
            unknownString4 = '\x00',
        )

        log.msg('PushNotificationSender: sendNotification')
        log.msg(repr(notification))
        self.sendMessageToDevice(pushToken, notification)
        return 'notification sent'
