import os
import random
import traceback
from uuid import UUID

from OpenSSL import SSL
from twisted.internet import reactor, ssl, protocol
from twisted.python import log

from icl0ud.push.dispatch import BaseDispatch
from icl0ud.push.parser import APSParser


class MessageProxy(protocol.Protocol, BaseDispatch, object):
    peer = None
    peer_type = None  # device or server

    def __init__(self):
        self._parser = APSParser()
        self._source = None
        self._buffer = b''

    def setPeer(self, peer):
        self.peer = peer

    def dataReceived(self, data):
        buff = self._buffer + data

        while self._parser.isMessageComplete(buff):
            message, length = self._parser.parseMessage(buff)
            messageData = buff[:length]
            buff = buff[length:]
            self.handleMessage(message, messageData)

        self._buffer = buff

    def handleMessage(self, message, data):
        forward = self.dispatch(self.peer_type, message)
        if forward:
            self.sendToPeer(data)

    def sendToPeer(self, data):
        self.peer.transport.write(data)

    def connectionLost(self, reason):
        # TODO notify handlers
        # FIXME fix this shutdown
        if self.peer is not None:
            self.peer.transport.loseConnection()
            self.peer = None
        else:
            log.msg("Unable to connect to peer: %s" % (reason,))


class InterceptClient(MessageProxy):
    """Proxy Client, captures iCloud-to-client traffic."""
    peer_type = 'server'

    def connectionMade(self):
        self.peer.connectedToServer(self)

    def getDeviceProtocol(self):
        return self.factory.deviceProtocol


class InterceptClientFactory(protocol.ClientFactory):

    protocol = InterceptClient

    def __init__(self, deviceProtocol):
        self.deviceProtocol = deviceProtocol

    def buildProtocol(self, *args, **kw):
        prot = protocol.ClientFactory.buildProtocol(self, *args, **kw)
        prot.setPeer(self.deviceProtocol)
        prot.addHandlers(self.dispatchHandlers)
        return prot

    def clientConnectionFailed(self, connector, reason):
        self.deviceProtocol.transport.loseConnection()

    def setDispatchHandlers(self, handlers):
        self.dispatchHandlers = handlers


class InterceptClientContextFactory(ssl.ClientContextFactory):

    def __init__(self, cert, chain):
        self.cert = cert
        self.chain = chain
        self.method = SSL.SSLv23_METHOD

    def _verifyCallback(self, conn, cert, errno, depth, preverifyOk):
        # FIXME we should check the server common name
        if not preverifyOk:
            log.err("Certificate validation failed.")
        return preverifyOk

    def getContext(self):
        ctx = ssl.ClientContextFactory.getContext(self)
        ctx.load_verify_locations(self.chain)
        ctx.use_certificate_file(self.cert)
        ctx.use_privatekey_file(self.cert)
        ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
            self._verifyCallback)
        return ctx


class InterceptServer(MessageProxy):
    """Proxy Server, captures client-to-iCloud traffic."""

    clientProtocolFactory = InterceptClientFactory
    peer_type = 'device'

    def __init__(self, *args, **kwargs):
        super(InterceptServer, self).__init__(*args, **kwargs)
        self.clientContextFactory = None
        self.deviceCommonName = None
        self._peerSendBuffer = b''

    def SSLInfoCallback(self, conn, where, ret):
        # TODO check why this callback is called two times with HANDSHAKE_DONE
        # - do not attempt to connect to server twice
        # SSL.SSL_CB_HANDSHAKE_DONE(0x20) is missing in old pyOpenSSL releases
        if where & 0x20:
            try:   # Catch exceptions since this function does not throw them
                try:
                    # Twisted < 11.1
                    cert = self.transport.socket.get_peer_certificate()
                except AttributeError:
                    # Twisted >= 11.1
                    cert = self.transport.getPeerCertificate()
                subject = dict(cert.get_subject().get_components())
                self.deviceCommonName = subject['CN']
                self.log('SSL handshake done: Device: %s' %
                         self.deviceCommonName)
                self.connectToServer()
            except Exception:
                log.err('[#%d] SSLInfoCallback Exception:' %
                        self.transport.sessionno)
                log.err(traceback.format_exc())

    def connectionMade(self):
        try:
            # Twisted < 11.1
            sslContext = self.transport.socket.get_context()
        except AttributeError:
            # Twisted >= 11.1
            # TODO Don't use private attribute _tlsConnection
            sslContext = self.transport._tlsConnection.get_context()
        sslContext.set_info_callback(self.SSLInfoCallback)
        peer = self.transport.getPeer()
        self.log('New connection from %s:%d' % (peer.host, peer.port))

    def connectToServer(self):
        # Don't read anything from the connecting client until we have
        # somewhere to send it to.
        self.transport.pauseProducing()
        clientFactory = self.getClientFactory()
        host = random.choice(self.factory.hosts)
        self.log('Connecting to push server: %s:%d' %
                 (host, self.factory.port))
        reactor.connectSSL(host,
                           self.factory.port,
                           clientFactory,
                           self.getClientContextFactory())

    def connectedToServer(self, peer):
        self.setPeer(peer)
        self.flushSendBuffer()
        self.transport.resumeProducing()

    def getDeviceProtocol(self):
        return self

    def sendToPeer(self, data):
        # This happens if connectToserver is not called fast enough to stop
        # the transport from producing. We send the buffer once the client
        # connection is established.
        if self.peer is None:
            self._peerSendBuffer += data
        else:
            super(InterceptServer, self).sendToPeer(data)

    def flushSendBuffer(self):
        self.sendToPeer(self._peerSendBuffer)
        self._peerSendBuffer = b''

    def getClientFactory(self, ):
        f = self.clientProtocolFactory(deviceProtocol=self)
        f.setDispatchHandlers(self.factory.dispatchHandlers)
        return f

    def getClientContextFactory(self):
        certDir = self.factory.clientCertDir
        # ensure this is a valid UUID, if not this throws an exception
        UUID(self.deviceCommonName)

        cert = os.path.join(certDir, self.deviceCommonName + '.pem')
        if not os.path.isfile(cert):
            raise Exception('Device certificate is missing: %s' % cert)

        if self.clientContextFactory is None:
            self.clientContextFactory = InterceptClientContextFactory(
                cert=cert,
                chain=self.factory.caCertChain,
            )
        return self.clientContextFactory

    def log(self, msg):
        prefix = '[#%d] ' % self.transport.sessionno
        log.msg(prefix + msg)


class InterceptServerFactory(protocol.Factory):

    protocol = InterceptServer
    serverContextFactory = None

    def __init__(self, hosts, port, serverCert, clientCertDir, caCertChain,
        serverChain, dispatchHandlers=[]):
        self.hosts = hosts
        self.port = port
        # Passing through the complete configuration seems quite ugly. Maybe
        # implement a Service?
        # The courier.push.apple.com server certificate
        self.serverCert = serverCert
        # Directory containing device certificates
        self.clientCertDir = clientCertDir
        # The cert chain for verifying Apple's server certificate
        self.caCertChain = caCertChain
        # The cert chain for verifying device certificates
        self.serverChain = serverChain

        self.dispatchHandlers = dispatchHandlers

    def buildProtocol(self, *args):
        p = protocol.Factory.buildProtocol(self, *args)
        p.addHandlers(self.dispatchHandlers)
        return p

    def getServerContextFactory(self):
        if self.serverContextFactory is None:
            self.serverContextFactory = InterceptServerContextFactory(
                self.serverCert,
                self.serverChain
            )
        return self.serverContextFactory


class InterceptServerContextFactory(ssl.DefaultOpenSSLContextFactory):
    def __init__(self, cert, chain):
        self.chain = chain
        ssl.DefaultOpenSSLContextFactory.__init__(self, cert, cert)

    def getContext(self):
        ctx = ssl.DefaultOpenSSLContextFactory.getContext(self)
        ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
            self._verifyCallback)
        ctx.load_verify_locations(self.chain)
        return ctx

    def _verifyCallback(self, conn, cert, errno, depth, preverifyOk):
        return preverifyOk
