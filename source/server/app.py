"""Threaded TCP server with one authoritative fixed-step simulation loop."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import logging
import math
import secrets
import socket
import threading
import time
import uuid
from common.config import TICK_RATE, SNAPSHOT_RATE, HEARTBEAT_TIMEOUT, PROTOCOL_VERSION
from common.protocol import FrameDecoder, ProtocolError, encode_packet, finite_number
from server.database import clean_text
from server.engine import Arena

LOG = logging.getLogger("slither")


@dataclass
class Room:
    id: str
    name: str
    host: str
    capacity: int = 8
    bots: int = 2
    members: dict = field(default_factory=dict)
    arena: object = None
    chat: deque = field(default_factory=lambda: deque(maxlen=40))

    def summary(self):
        return {"id": self.id, "name": self.name, "host": self.host,
                "players": len(self.members), "capacity": self.capacity,
                "status": "PLAYING" if self.arena else "WAITING", "bots": self.bots}

    def state(self):
        return {"type": "ROOM_STATE", **self.summary(),
                "members": [{"id": pid, "name": s.user["display_name"],
                             "color": s.user["skin_color"]} for pid,s in self.members.items()],
                "chat": list(self.chat)}


class Session:
    """Reader + writer threads per connection. Obsolete snapshots are replaced.

    Never sendall while holding the global server lock. A slow client cannot
    make the physics loop wait on network I/O.
    """
    def __init__(self, app, sock, address):
        self.app, self.sock, self.address = app, sock, address
        self.user = None
        self.room_id = None
        self.token = None
        self.closed = False
        self.last_seen = time.monotonic()
        self.last_auth = -100.0
        self.last_input = 0
        self.last_chat = 0
        self.sequence = -1
        self.window_start = time.monotonic()
        self.window_count = 0
        self.pending = deque()
        self.latest_world = None
        self.condition = threading.Condition()
        sock.settimeout(1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    @property
    def pid(self):
        return str(self.user["id"]) if self.user else None

    def send(self, message):
        data = encode_packet(message)
        overflow = False
        with self.condition:
            if self.closed:
                return
            if message["type"] == "WORLD_STATE":
                self.latest_world = data
            elif len(self.pending) < 128:
                self.pending.append(data)
            else:
                overflow = True
            self.condition.notify()
        if overflow:
            self.close()

    def start(self):
        threading.Thread(target=self._writer, daemon=True, name="send-client").start()
        threading.Thread(target=self._reader, daemon=True, name="recv-client").start()

    def _writer(self):
        try:
            while not self.closed:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.pending or self.latest_world)
                    if self.closed:
                        break
                    if self.pending:
                        data = self.pending.popleft()
                    else:
                        data, self.latest_world = self.latest_world, None
                self.sock.sendall(data)
        except OSError:
            pass
        finally:
            self.close()

    def _reader(self):
        parser = FrameDecoder(max_frame=8192)
        try:
            while not self.closed:
                try:
                    data = self.sock.recv(16384)
                except socket.timeout:
                    if time.monotonic()-self.last_seen > HEARTBEAT_TIMEOUT:
                        break
                    continue
                if not data:
                    break
                for message in parser.feed(data):
                    now = time.monotonic()
                    self.last_seen = now
                    if now-self.window_start >= 1:
                        self.window_start, self.window_count = now, 0
                    self.window_count += 1
                    if self.window_count > 150:
                        raise ProtocolError("Rate limit exceeded")
                    try:
                        self.app.handle(self, message)
                    except (ValueError, ProtocolError) as exc:
                        self.send({"type": "ERROR", "message": str(exc)})
                    except Exception:
                        LOG.exception("Request failed for %s", self.address)
                        self.send({"type": "ERROR", "message": "Máy chủ không xử lý được yêu cầu. Xem log server."})
        except (OSError, ProtocolError):
            pass
        finally:
            self.close()

    def close(self):
        with self.condition:
            if self.closed:
                return
            self.closed = True
            self.condition.notify_all()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.app.disconnected(self)


class GameServer:
    def __init__(self, database, host="127.0.0.1", port=5555):
        self.db, self.host, self.port = database, host, port
        self.lock = threading.RLock()
        self.sessions, self.users, self.rooms, self.tokens = set(), {}, {}, {}
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.listener = None
        self.db_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="database-writer")
        self.tick_ms = 0
        self.db.close_old_rooms()

    def persist(self, function, *args):
        def job():
            for attempt in range(3):
                try:
                    function(*args)
                    return
                except Exception:
                    LOG.exception("Database write failed (attempt %s)", attempt+1)
                    time.sleep(.15*(attempt+1))
            LOG.error("Database write exhausted retries; inspect server.log before stopping.")
        if not self.stop_event.is_set():
            self.db_worker.submit(job)

    def serve_forever(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(64)
        self.listener.settimeout(.5)
        self.ready.set()
        LOG.info("LISTEN %s:%s | physics=%s Hz snapshot=%s Hz | db=%s", self.host, self.port, TICK_RATE, SNAPSHOT_RATE, self.db.mode)
        threading.Thread(target=self._simulation, daemon=True, name="physics").start()
        try:
            while not self.stop_event.is_set():
                try:
                    sock, address = self.listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self.lock:
                    if len(self.sessions) >= 64:
                        sock.close()
                        continue
                    session = Session(self, sock, address)
                    self.sessions.add(session)
                    session.start()
                    session.send({"type": "HELLO", "protocol": PROTOCOL_VERSION})
        finally:
            self.shutdown()

    def _simulation(self):
        next_tick = time.monotonic()
        tick = 0
        while not self.stop_event.is_set():
            start = time.monotonic()
            try:
                with self.lock:
                    for room in list(self.rooms.values()):
                        if not room.arena:
                            continue
                        room.arena.update(1/TICK_RATE)
                        self._collect(room)
                        if tick % (TICK_RATE//SNAPSHOT_RATE) == 0:
                            world = room.arena.snapshot()
                            world["room_id"] = room.id
                            for session in list(room.members.values()):
                                session.send(world)
                    if tick % (TICK_RATE*5) == 0:
                        now = time.monotonic()
                        self.tokens = {t: info for t,info in self.tokens.items()
                                       if info[1] > now or info[0] in self.users}
                        LOG.info("STATUS connections=%d users=%d rooms=%d tick_ms=%.2f", len(self.sessions), len(self.users), len(self.rooms), self.tick_ms)
            except Exception:
                LOG.exception("Simulation tick failed")
            self.tick_ms = (time.monotonic()-start)*1000
            tick += 1
            next_tick += 1/TICK_RATE
            self.stop_event.wait(max(0, next_tick-time.monotonic()))
            if time.monotonic()-next_tick > .25:
                # Drop accumulated lag instead of unbounded catch-up ticks.
                next_tick = time.monotonic()

    def _collect(self, room):
        for event in room.arena.drain_events():
            if not event["bot"]:
                self.persist(self.db.save_match, int(event["id"]), room.id, event)
                session = room.members.get(event["id"])
                if session:
                    session.user["highest_score"] = max(session.user["highest_score"], event["score"])
                    session.send({"type": "DEATH", **event})
            LOG.info("DEATH room=%s player=%s reason=%s peak=%d", room.id, event["id"], event["reason"], event["score"])

    def _room(self, session):
        room = self.rooms.get(session.room_id)
        if not room:
            raise ValueError("Bạn chưa ở trong phòng.")
        return room

    def _broadcast_room(self, room):
        for s in list(room.members.values()):
            s.send(room.state())

    def _lobby(self, session):
        session.send({"type": "LOBBY", "rooms": [r.summary() for r in self.rooms.values()], "user": session.user})

    def _broadcast_lobby(self):
        for s in list(self.users.values()):
            if not s.room_id:
                self._lobby(s)

    def _leave(self, session, reason="leave"):
        room = self.rooms.get(session.room_id)
        session.room_id = None
        session.sequence = -1
        with session.condition:
            session.latest_world = None
        if not room:
            return
        if room.arena:
            room.arena.remove(session.pid, reason)
            self._collect(room)
        room.members.pop(session.pid, None)
        if not room.members:
            del self.rooms[room.id]
            self.persist(self.db.room_status, room.id, "CLOSED")
        else:
            if room.host == session.pid:
                room.host = next(iter(room.members))
            self._broadcast_room(room)
        self._broadcast_lobby()

    def disconnected(self, session):
        with self.lock:
            self.sessions.discard(session)
            if session.user and self.users.get(session.pid) is session:
                self._leave(session, "disconnect")
                self.users.pop(session.pid, None)
                if session.token:
                    self.tokens[session.token] = (session.pid, time.monotonic()+120)
            LOG.info("DISCONNECT %s", session.address)

    def _authenticate(self, session, message):
        now = time.monotonic()
        if now-session.last_auth < .6:
            raise ValueError("Vui lòng đợi một chút trước khi đăng nhập lại.")
        session.last_auth = now
        if session.user:
            raise ValueError("Bạn đã đăng nhập.")
        kind = message["type"]
        if kind == "RESUME":
            with self.lock:
                token = message.get("token", "")
                if not isinstance(token, str):
                    raise ValueError("Phiên không hợp lệ.")
                info = self.tokens.get(token)
                if not info or (info[1] < now and info[0] not in self.users):
                    session.send({"type": "AUTH_EXPIRED"})
                    return
                user = self.db.profile(int(info[0]))
        elif kind == "REGISTER":
            user = self.db.register(message.get("username"), message.get("password"), message.get("name"))
        else:
            user = self.db.login(message.get("username"), message.get("password"))
        # Password hashing is outside the simulation lock.
        with self.lock:
            if session.closed:
                return
            pid = str(user["id"])
            if pid in self.users:
                if kind == "RESUME":
                    self.users[pid].close()
                else:
                    raise ValueError("Tài khoản đang được sử dụng trên kết nối khác.")
            self.tokens = {t:v for t,v in self.tokens.items() if v[0] != pid}
            session.user, session.token = user, secrets.token_urlsafe(32)
            self.users[pid] = session
            self.tokens[session.token] = (pid, now+120)
            session.send({"type": "AUTH_OK", "user": user, "token": session.token, "resumed": kind == "RESUME"})
            self._lobby(session)

    def handle(self, session, message):
        kind = message["type"]
        if kind == "PING":
            stamp = finite_number(message.get("stamp", 0), 0, 1e15)
            session.send({"type": "PONG", "stamp": stamp})
            return
        if kind in ("REGISTER", "LOGIN", "RESUME"):
            self._authenticate(session, message)
            return
        if not session.user:
            raise ValueError("Vui lòng đăng nhập trước.")
        # Read-only DB requests do not hold the physics lock.
        if kind == "LEADERBOARD":
            session.send({"type": "LEADERBOARD", "rows": self.db.leaderboard()})
            return
        if kind == "HISTORY":
            session.send({"type": "HISTORY", "rows": self.db.history(session.user["id"])})
            return
        with self.lock:
            if kind == "LIST_ROOMS":
                self._lobby(session)
            elif kind == "PROFILE":
                if session.room_id:
                    raise ValueError("Hãy đổi hồ sơ ở sảnh chính.")
                session.user = self.db.update_profile(session.user["id"], message.get("name"), message.get("skin"))
                session.send({"type": "PROFILE_OK", "user": session.user})
            elif kind == "CREATE_ROOM":
                if session.room_id:
                    raise ValueError("Hãy rời phòng hiện tại trước.")
                if len(self.rooms) >= 16:
                    raise ValueError("Máy chủ đã đủ 16 phòng.")
                name = clean_text(message.get("name", "Đấu trường mới"), 32)
                capacity = int(finite_number(message.get("capacity", 8), 2, 8))
                bots = int(finite_number(message.get("bots", 2), 0, 4))
                rid = uuid.uuid4().hex[:12]
                self.db.create_room(rid, name, session.user["id"], capacity)
                room = Room(rid, name, session.pid, capacity, bots)
                self.rooms[rid] = room
                room.members[session.pid] = session
                session.room_id = rid
                self._broadcast_room(room)
                self._broadcast_lobby()
            elif kind in ("JOIN_ROOM", "QUICK_JOIN"):
                if session.room_id:
                    raise ValueError("Hãy rời phòng hiện tại trước.")
                if kind == "QUICK_JOIN":
                    room = next((r for r in self.rooms.values() if len(r.members)<r.capacity), None)
                    if room is None:
                        self.handle(session, {"type": "CREATE_ROOM", "name": "Đấu trường nhanh", "bots": 2})
                        return
                else:
                    room = self.rooms.get(str(message.get("room_id")))
                if not room or len(room.members) >= room.capacity:
                    raise ValueError("Phòng đã đầy hoặc không còn tồn tại.")
                room.members[session.pid] = session
                session.room_id = room.id
                if room.arena:
                    room.arena.spawn(session.pid, session.user["display_name"], session.user["skin_color"])
                self._broadcast_room(room)
                self._broadcast_lobby()
            elif kind == "START_GAME":
                room = self._room(session)
                if room.host != session.pid:
                    raise ValueError("Chỉ chủ phòng được bắt đầu trận.")
                if not room.arena:
                    room.arena = Arena()
                    for s in room.members.values():
                        room.arena.spawn(s.pid, s.user["display_name"], s.user["skin_color"])
                    room.arena.add_bots(room.bots)
                    self.persist(self.db.room_status, room.id, "PLAYING")
                    self._broadcast_room(room)
                    self._broadcast_lobby()
            elif kind == "PLAYER_INPUT":
                room = self._room(session)
                if not room.arena:
                    return
                angle = finite_number(message.get("angle"), -math.tau*2, math.tau*2)
                boost = message.get("boost", False)
                seq = message.get("seq", 0)
                if not isinstance(boost, bool) or type(seq) is not int or not 0 <= seq < 2**53:
                    raise ValueError("Input không hợp lệ.")
                now = time.monotonic()
                if seq <= session.sequence or now-session.last_input < 1/90:
                    return
                session.sequence, session.last_input = seq, now
                room.arena.set_input(session.pid, angle, boost)
            elif kind == "RESPAWN":
                room = self._room(session)
                if not room.arena:
                    raise ValueError("Trận chưa bắt đầu.")
                snake = room.arena.snakes.get(session.pid)
                if snake and snake.alive:
                    return
                room.arena.spawn(session.pid, session.user["display_name"], session.user["skin_color"])
                session.send({"type": "RESPAWN_OK"})
            elif kind == "CHAT":
                room = self._room(session)
                if time.monotonic()-session.last_chat < .5:
                    raise ValueError("Bạn đang gửi tin nhắn quá nhanh.")
                content = clean_text(message.get("text"), 160)
                session.last_chat = time.monotonic()
                entry = {"name": session.user["display_name"], "text": content}
                room.chat.append(entry)
                for s in room.members.values():
                    s.send({"type": "CHAT", **entry})
            elif kind == "KICK":
                room = self._room(session)
                if room.host != session.pid or room.arena:
                    raise ValueError("Chỉ chủ phòng được mời người khác ra ở phòng chờ.")
                target = room.members.get(str(message.get("player_id")))
                if not target or target is session:
                    raise ValueError("Người chơi không hợp lệ.")
                self._leave(target, "kick")
                target.send({"type": "KICKED", "message": "Chủ phòng đã mời bạn ra khỏi phòng."})
                self._lobby(target)
            elif kind == "LEAVE_ROOM":
                self._leave(session)
                session.send({"type": "LEFT_ROOM"})
                self._lobby(session)
            elif kind == "LOGOUT":
                self._leave(session)
                self.users.pop(session.pid, None)
                self.tokens.pop(session.token, None)
                session.user, session.token = None, None
                session.send({"type": "LOGGED_OUT"})
            else:
                raise ValueError("Loại gói tin không được hỗ trợ.")

    def status(self):
        with self.lock:
            return {"connections": len(self.sessions), "tick_ms": round(self.tick_ms, 2),
                    "rooms": [{**r.summary(), "heads": {
                        s.name: [round(v) for v in s.head] for s in r.arena.snakes.values() if s.alive}
                        if r.arena else {}} for r in self.rooms.values()]}

    def kick_username(self, username):
        with self.lock:
            for session in list(self.users.values()):
                if session.user["username"] == username.lower():
                    session.close()
                    return True
        return False

    def shutdown(self):
        with self.lock:
            if self.stop_event.is_set():
                return
            # Queue match writes before setting stop_event.
            for session in list(self.sessions):
                session.close()
            self.stop_event.set()
            if self.listener:
                self.listener.close()
        self.db_worker.shutdown(wait=True)
        LOG.info("Server stopped; pending database writes flushed.")
