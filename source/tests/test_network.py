"""End-to-end tests over real localhost TCP sockets; no mocks for transport."""
from pathlib import Path
import math
import socket
import tempfile
import threading
import time
import unittest
from common.protocol import FrameDecoder,encode_packet
from server.app import GameServer
from server.database import Database


class Wire:
    def __init__(self,port):
        self.sock=socket.create_connection(("127.0.0.1",port),2)
        self.sock.settimeout(.3)
        self.parser=FrameDecoder(); self.messages=[]
    def send(self,kind,**kwargs): self.sock.sendall(encode_packet({"type":kind,**kwargs}))
    def until(self,kind,timeout=4):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            for i,m in enumerate(self.messages):
                if m["type"]==kind: return self.messages.pop(i)
            try: data=self.sock.recv(65536)
            except socket.timeout: continue
            if not data: raise AssertionError("Disconnected while waiting for "+kind)
            self.messages.extend(self.parser.feed(data))
        raise AssertionError("Timed out waiting for "+kind+"; pending="+str([m['type'] for m in self.messages]))
    def close(self):
        try: self.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.sock.close()


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database(path=Path(self.tmp.name)/"test.db")
        self.server=GameServer(self.db,port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.assertTrue(self.server.ready.wait(3))
        self.clients=[]
    def tearDown(self):
        for c in self.clients: c.close()
        self.server.shutdown(); self.thread.join(3); self.tmp.cleanup()
    def client(self,name):
        c=Wire(self.server.port); self.clients.append(c)
        c.send("REGISTER",username=name,password="testpass123",name=name)
        c.auth=c.until("AUTH_OK"); c.until("LOBBY")
        return c
    def room_pair(self):
        a,b=self.client("pilot_one"),self.client("pilot_two")
        a.send("CREATE_ROOM",name="Test room",capacity=2,bots=0); room=a.until("ROOM_STATE")
        b.send("JOIN_ROOM",room_id=room["id"]); b.until("ROOM_STATE"); a.until("ROOM_STATE")
        return a,b,room

    def test_room_chat_host_start_and_shared_state(self):
        a,b,room=self.room_pair()
        b.send("CHAT",text="Xin chào, phòng thử nghiệm!")
        self.assertEqual(a.until("CHAT")["text"],b.until("CHAT")["text"])
        b.send("START_GAME")
        self.assertIn("chủ phòng",b.until("ERROR")["message"])
        a.send("START_GAME")
        wa,wb=a.until("WORLD_STATE"),b.until("WORLD_STATE")
        self.assertEqual({s["id"] for s in wa["snakes"]},{s["id"] for s in wb["snakes"]})
        self.assertEqual(len(wa["snakes"]),2)

    def test_server_ignores_forged_position_score_and_player_id(self):
        a,b,room=self.room_pair(); a.send("START_GAME"); a.until("WORLD_STATE")
        a.send("PLAYER_INPUT",angle=0,boost=False,seq=1,x=999999,score=999999,player_id=b.auth["user"]["id"])
        time.sleep(.12)
        with self.server.lock:
            snake=self.server.rooms[room["id"]].arena.snakes[str(a.auth["user"]["id"])]
            self.assertLess(snake.head[0],3000)
            self.assertLess(snake.score,100)
        a.send("PLAYER_INPUT",angle="nan",boost=False,seq=2)
        self.assertEqual(a.until("ERROR")["type"],"ERROR")

    def test_death_respawn_history_and_cleanup(self):
        a,b,room=self.room_pair(); a.send("START_GAME"); a.until("WORLD_STATE")
        pid=str(a.auth["user"]["id"])
        with self.server.lock:
            snake=self.server.rooms[room["id"]].arena.snakes[pid]
            snake.body[0]=(2986,1000); snake.angle=snake.target=0; snake.score=snake.peak_score=12
        death=a.until("DEATH")
        self.assertEqual(death["reason"],"wall")
        a.send("RESPAWN"); a.until("RESPAWN_OK")
        with self.server.lock: self.assertTrue(self.server.rooms[room["id"]].arena.snakes[pid].alive)
        self.server.db_worker.submit(lambda:None).result(3)
        a.send("HISTORY")
        self.assertEqual(a.until("HISTORY")["rows"][0]["score"],12)
        a.send("LEAVE_ROOM"); a.until("LEFT_ROOM")
        with self.server.lock: self.assertNotIn(pid,self.server.rooms[room["id"]].members)

    def test_room_capacity_host_transfer_and_kick(self):
        a,b,room=self.room_pair(); c=self.client("pilot_three")
        c.send("JOIN_ROOM",room_id=room["id"]); self.assertIn("đầy",c.until("ERROR")["message"])
        a.send("KICK",player_id=b.auth["user"]["id"]); b.until("KICKED")
        c.send("JOIN_ROOM",room_id=room["id"]); c.until("ROOM_STATE")
        a.send("LEAVE_ROOM"); a.until("LEFT_ROOM")
        with self.server.lock: self.assertEqual(self.server.rooms[room["id"]].host,str(c.auth["user"]["id"]))

    def test_resume_after_disconnect(self):
        a=self.client("pilot_one"); token=a.auth["token"]; a.close(); self.clients.remove(a)
        end=time.monotonic()+2
        while self.server.users and time.monotonic()<end: time.sleep(.01)
        b=Wire(self.server.port); self.clients.append(b)
        b.send("RESUME",token=token)
        auth=b.until("AUTH_OK")
        self.assertTrue(auth["resumed"])
        self.assertNotEqual(auth["token"],token)
        self.assertEqual(auth["user"]["username"],"pilot_one")

    def test_fragmented_auth_and_unauthenticated_access(self):
        c=Wire(self.server.port); self.clients.append(c)
        c.send("CREATE_ROOM",name="Invalid"); self.assertIn("đăng nhập",c.until("ERROR")["message"])
        data=encode_packet({"type":"REGISTER","username":"fragmented","password":"testpass123","name":"Tiếng Việt"})
        for start in range(0,len(data),3): c.sock.sendall(data[start:start+3])
        self.assertEqual(c.until("AUTH_OK")["user"]["display_name"],"Tiếng Việt")

    def test_bad_frame_disconnect_does_not_stop_server(self):
        a=self.client("pilot_one")
        bad=Wire(self.server.port); self.clients.append(bad); bad.until("HELLO")
        bad.sock.sendall(b'[]\n')
        self.assertEqual(bad.sock.recv(100),b'')
        a.send("PING",stamp=123)
        self.assertEqual(a.until("PONG")["stamp"],123)
