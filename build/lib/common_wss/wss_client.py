# coding=utf-8
import threading
import json
import hmac
import hashlib
from autobahn.twisted.websocket import WebSocketClientFactory, \
    WebSocketClientProtocol, \
    connectWS
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet.error import ReactorAlreadyRunning


class ClientProtocol(WebSocketClientProtocol):

    def __init__(self, factory, payload=None):
        super().__init__()
        self.factory = factory
        self.payload = payload

    def onOpen(self):
        self.factory.protocol_instance = self

    def onConnect(self, response):
        if self.payload:
            self.sendMessage(self.payload, isBinary=False)
        # reset the delay after reconnecting
        self.factory.resetDelay()

    def onMessage(self, payload, isBinary):
        if not isBinary:
            try:
                payload_obj = json.loads(payload.decode('utf8'))
            except ValueError:
                pass
            else:
                self.factory.callback(payload_obj)


class ClientReconnectingFactory(ReconnectingClientFactory):

    # set initial delay to a short time
    initialDelay = 0.1

    maxDelay = 20

    maxRetries = 30


class ClientFactory(WebSocketClientFactory, ClientReconnectingFactory):

    def __init__(self, *args, payload=None, **kwargs):
        WebSocketClientFactory.__init__(self, *args, **kwargs)
        self.protocol_instance = None
        self.base_client = None
        self.payload = payload

    protocol = ClientProtocol
    _reconnect_error_payload = {
        'e': 'error',
        'm': 'Max reconnect retries reached'
    }

    def clientConnectionFailed(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def clientConnectionLost(self, connector, reason):
        self.retry(connector)
        if self.retries > self.maxRetries:
            self.callback(self._reconnect_error_payload)

    def buildProtocol(self, addr):
        return ClientProtocol(self, payload=self.payload)


class SocketManager(threading.Thread):


    def __init__(self, stream_url):  # client
        threading.Thread.__init__(self)
        self.factories = {}
        self._connected_event = threading.Event()
        self._conns = {}
        self._user_timer = None
        self._user_listen_key = None
        self._user_callback = None
        self.STREAM_URL = stream_url

    def _start_socket(self, id_, payload, callback):
        if id_ in self._conns:
            return False

        factory_url = self.STREAM_URL
        factory = ClientFactory(factory_url, payload=payload)
        factory.base_client = self
        factory.protocol = ClientProtocol
        factory.callback = callback
        factory.reconnect = True
        self.factories[id_] = factory
        reactor.callFromThread(self.add_connection, id_)

    def add_connection(self, id_):
        """
        Convenience function to connect and store the resulting
        connector.
        """
        factory = self.factories[id_]
        context_factory = ssl.ClientContextFactory()
        self._conns[id_] = connectWS(factory, context_factory)

    def stop_socket(self, conn_key):
        """Stop a websocket given the connection key

        Parameters
        ----------
        conn_key : str
            Socket connection key

        Returns
        -------
        str, bool
            connection key string if successful, False otherwise
        """
        if conn_key not in self._conns:
            return

        # disable reconnecting if we are closing
        self._conns[conn_key].factory = WebSocketClientFactory(self.STREAM_URL)
        self._conns[conn_key].disconnect()
        del self._conns[conn_key]

    def run(self):
        try:
            reactor.run(installSignalHandlers=False)
        except ReactorAlreadyRunning:
            # Ignore error about reactor already running
            pass

    def close(self):
        """Close all connections
        """
        keys = set(self._conns.keys())
        for key in keys:
            self.stop_socket(key)
        self._conns = {}


class WssClient(SocketManager):
    def __init__(self, stream_url, key=None, secret=None, nonce_multiplier=1.0):  # client
        super().__init__(stream_url)
        self.key = key
        self.secret = secret
        self.nonce_multiplier = nonce_multiplier

    def stop(self):
        """Tries to close all connections and finally stops the reactor.
        Properly stops the program."""
        try:
            self.close()
        finally:
            reactor.stop()

    def subscribe_public(self, data, id_, callback):
        payload = json.dumps(data, ensure_ascii=False).encode('utf8')
        return self._start_socket(id_, payload, callback)


