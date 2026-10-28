"""Background transport; no socket operation blocks the Pygame event loop."""
from collections import deque
import socket
import threading
import time
from common.protocol import FrameDecoder, encode_packet, ProtocolError


class Network:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.token = None
        self.connected = False
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.outgoing, self.incoming = deque(), deque()
        self.latest_input = None
        self.sock = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="network-client")

    def start(self):
        self.thread.start()

    def send(self, kind, **data):
        packet = {"type": kind, **data}
        with self.lock:
            if kind == "PLAYER_INPUT":
                self.latest_input = packet
            elif len(self.outgoing) < 128:
                self.outgoing.append(packet)

    def _post(self, message):
        with self.lock:
            if len(self.incoming) >= 256:
                # Drop an obsolete world before any control event.
                stale = next((i for i,m in enumerate(self.incoming) if m["type"] == "WORLD_STATE"), None)
                if stale is not None:
                    del self.incoming[stale]
                else:
                    self.incoming.popleft()
            message["_received"] = time.monotonic()
            self.incoming.append(message)

    def poll(self):
        with self.lock:
            messages = list(self.incoming)
            self.incoming.clear()
            return messages

    def _run(self):
        attempts, ever_connected = 0, False
        while not self.stop.is_set():
            self._post({"type": "NET_CONNECTING", "attempt": attempts})
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=3)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.sock.settimeout(.02)
                parser = FrameDecoder()
                self.connected = True
                self._post({"type": "NET_CONNECTED"})
                if self.token:
                    self.sock.sendall(encode_packet({"type": "RESUME", "token": self.token}))
                last_ping = 0
                last_seen = time.monotonic()
                connected_since = last_seen
                ever_connected = True
                while not self.stop.is_set():
                    now = time.monotonic()
                    if now-last_seen > 8:
                        raise OSError("Heartbeat timeout")
                    if now-connected_since > 5:
                        attempts = 0
                    with self.lock:
                        packets = list(self.outgoing)
                        self.outgoing.clear()
                        if self.latest_input:
                            packets.append(self.latest_input)
                            self.latest_input = None
                    if now-last_ping >= 2:
                        packets.append({"type": "PING", "stamp": now})
                        last_ping = now
                    if packets:
                        self.sock.settimeout(1)
                        self.sock.sendall(b"".join(encode_packet(p) for p in packets))
                        self.sock.settimeout(.02)
                    try:
                        chunk = self.sock.recv(65536)
                    except socket.timeout:
                        continue
                    if not chunk:
                        raise OSError("Server closed connection")
                    for message in parser.feed(chunk):
                        last_seen = time.monotonic()
                        if message["type"] == "AUTH_OK":
                            self.token = message["token"]
                        elif message["type"] in ("AUTH_EXPIRED", "LOGGED_OUT"):
                            self.token = None
                        self._post(message)
            except (OSError, ValueError, ProtocolError):
                pass
            finally:
                self.connected = False
                if self.sock:
                    try:
                        self.sock.close()
                    except OSError:
                        pass
                with self.lock:
                    self.outgoing.clear()
                    self.latest_input = None
            if self.stop.is_set():
                return
            if not ever_connected or attempts >= 3:
                self._post({"type": "NET_FAILED"})
                return
            attempts += 1
            self._post({"type": "NET_RETRY", "attempt": attempts})
            if self.stop.wait(attempts):
                return

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
