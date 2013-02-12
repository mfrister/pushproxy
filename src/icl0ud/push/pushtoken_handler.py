from icl0ud.push.dispatch import BaseHandler
from icl0ud.push.messages import APSConnectBase


class PushTokenHandler(BaseHandler):
    def __init__(self):
        self.tokenProtocolMap = {}

    def handle(self, source, message, deviceProtocol):
        if not isinstance(message, APSConnectBase):
            return
        self.updatePushToken(deviceProtocol, message.pushToken)

    def updatePushToken(self, deviceProtocol, pushToken):
        # FIXME check whether all of this works for multiple users on one Mac
        # see applepushserviced log, e.g. sending filter message ...
        # with token ... for user ...
        # - there is one device/root token and another for each user
        # - multiple APSConnect/-Response messages, one for each token
        # - multiple APSTopics messages, one for each token
        # We need to remove old tokens at some point.
        # TODO limit tokens per device?
        if pushToken is None:
            return

        isNewToken = not pushToken in self.tokenProtocolMap

        if isNewToken:
            msg = 'New push token: %s' % pushToken.encode('hex')
            deviceProtocol.log(self.__class__.__name__ + ': ' + msg)

        self.tokenProtocolMap[pushToken] = deviceProtocol

    def deviceProtocolForToken(self, pushToken):
        return self.tokenProtocolMap[pushToken]
