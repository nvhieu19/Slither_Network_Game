"""Reproducible real-server GUI smoke test and screenshots in SDL dummy mode.

Run: python -m tools.gui_smoke --out PATH
Screenshots are from the running application; the test controls the server only
to make a repeatable death/respawn event, not to fake screenshots or outcomes.
"""
import argparse
import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy")
os.environ.setdefault("SDL_AUDIODRIVER","dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT","1")
from pathlib import Path
import tempfile
import threading
import time
import pygame
from server.app import GameServer
from server.database import Database
from client.app import App
from tests.test_network import Wire


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--out",default="data/screenshots"); args=parser.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db=Database(path=Path(tmp)/"demo.db")
        server=GameServer(db,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        assert server.ready.wait(3)
        app=App(port=server.port)
        friend=None
        def frames_until(predicate,timeout=5):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                app.frame()
                if predicate(): return
            raise AssertionError("GUI condition timed out: "+app.scene+" / "+app.toast_value)
        def capture(name):
            app.toast_until=0
            app.draw(time.monotonic(),1/60)
            pygame.image.save(app.canvas,str(out/(name+".png")))
        try:
            app.frame(); capture("01_dang_nhap")
            app.register_mode=True
            app.fields["username"].value="neon_pilot"
            app.fields["password"].value="demo_password123"
            app.fields["display"].value="Neon Pilot"
            app.authenticate(); frames_until(lambda:app.scene=="lobby")
            app.fields["profile"].value="Neon Pilot"
            app.skin="#54E8B0"; app.send("PROFILE",name="Neon Pilot",skin=app.skin)
            capture("02_sanh_chinh")
            app.fields["room"].value="Neon Arena"
            app.bots=4
            app.create_room(); frames_until(lambda:app.scene=="room")
            friend=Wire(server.port)
            friend.send("REGISTER",username="comet_pilot",password="demo_password123",name="Comet Pilot")
            auth=friend.until("AUTH_OK")
            friend.send("JOIN_ROOM",room_id=app.room["id"]); friend.until("ROOM_STATE")
            friend.send("CHAT",text="Sẵn sàng! Cùng vào đấu trường nhé.")
            frames_until(lambda:len(app.room["members"])==2 and len(app.chat)>0)
            capture("03_phong_cho")
            app.send("START_GAME"); frames_until(lambda:bool(app.world.states))
            # Position actual server entities near one another for visual inspection.
            # Positions still move and broadcast through the normal TCP path.
            with server.lock:
                arena=server.rooms[app.room["id"]].arena
                for i,s in enumerate(arena.snakes.values()):
                    x,y=1500+(i%3-1)*220,1500+(i//3)*180
                    s.body=[(x-j*6,y+20*__import__('math').sin(j*.16)) for j in range(40)]
                    s.score=s.peak_score=44
                    s.angle=s.target=0
                    s.shield=2
                for i in range(50):
                    arena.add_food(1150+(i*71)%900,1300+(i*61)%600,1)
            start=time.monotonic()
            frames_until(lambda:time.monotonic()-start>.5)
            capture("04_dau_truong")
            with server.lock:
                s=server.rooms[app.room["id"]].arena.snakes[app.pid]
                s.body[0]=(2990,1500); s.angle=s.target=0
            frames_until(lambda:app.dead is not None)
            capture("05_ket_qua")
            app.send("RESPAWN"); frames_until(lambda:app.dead is None and bool(app.world.states))
            app.send("LEAVE_ROOM"); frames_until(lambda:app.scene=="lobby")
            server.db_worker.submit(lambda:None).result(3)
            app.open_modal("history"); frames_until(lambda:bool(app.history))
            capture("06_lich_su")
            # Force a transport failure while the server stays alive: token resume.
            with server.lock: server.users[app.pid].close()
            start=time.monotonic()
            frames_until(lambda:time.monotonic()-start>1.5 and app.scene=="lobby" and app.net.connected,timeout=7)
            assert app.user["username"]=="neon_pilot"
            print("GUI PASS: register, profile, room, chat, live game, death, respawn, history, reconnect.")
            print("Screenshots:",out.resolve())
        finally:
            if app.net: app.net.close()
            if friend: friend.close()
            server.shutdown(); thread.join(3); pygame.quit()


if __name__=="__main__": main()
