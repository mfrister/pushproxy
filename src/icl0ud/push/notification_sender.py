import random
from datetime import datetime, timedelta
from struct import pack

from twisted.spread import pb

from icl0ud.push.dispatch import BaseHandler
from icl0ud.push.messages import APSNotification, APSNotificationResponse

# FIXME rename this module


class PushNotificationSender(BaseHandler, pb.Root):
    def __init__(self, tokenHandler):
        self._tokenHandler = tokenHandler
        self._messageIds = {}

    def handle(self, source, message, deviceProtocol):
        if not isinstance(message, APSNotificationResponse):
            return True
        if message.messageId in self._messageIds:
            deviceProtocol.log('PushNotificationSender: Found message with ' +
                               'self-issued response token: %s'
                                % repr(message))
            del self._messageIds[message.messageId]
            return False
        return True

    def sendMessageToDevice(self, pushToken, message):
        deviceProtocol = self._tokenHandler.deviceProtocolForToken(pushToken)
        data = message.marshal()
        deviceProtocol.log('PushNotificationSender: Sending to device: ' +
                           str(message))
        deviceProtocol.transport.write(data)

    def generatemessageId(self):
        token = None
        while token in self._messageIds or token is None:
            token = pack("!L", random.randint(0, 2 ** 32 - 1))
        self._messageIds[token] = True
        return token

    def remote_sendNotification(self, pushToken, topic, payload):
        notification = APSNotification(
            recipientPushToken=pushToken,
            topic=topic,
            payload=payload,
            messageId=self.generatemessageId(),
            expires=datetime.now() + timedelta(days=1),
            timestamp=datetime.now(),
            storageFlags='\x00',
        )
        self.sendMessageToDevice(pushToken, notification)
        return 'notification sent'
