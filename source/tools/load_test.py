"""Short localhost load sample. This is not a WAN/Internet capacity guarantee."""
import argparse
from pathlib import Path
import json
import math
import platform
import statistics
import tempfile
import threading
import time
from common.protocol import encode_packet
from server.app import GameServer
from server.database import Database
from tests.test_network import Wire


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--seconds",type=float,default=10)
    parser.add_argument("--out",default="data/load_result.json"); args=parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        server=GameServer(Database(path=Path(tmp)/"load.db"),port=0)
        runner=threading.Thread(target=server.serve_forever,daemon=True); runner.start(); server.ready.wait(3)
        clients=[]; samples=[]; sizes=[]; tick_count=[0]*8; failures=[]
        stop=threading.Event()
        workers=[]
        try:
            for i in range(8):
                c=Wire(server.port); clients.append(c)
                c.send("REGISTER",username=f"load_{i}",password="load_test_password",name=f"Player {i+1}")
                c.auth=c.until("AUTH_OK"); c.until("LOBBY")
            host=clients[0]; host.send("CREATE_ROOM",name="Load test",capacity=8,bots=4); room=host.until("ROOM_STATE")
            for c in clients[1:]: c.send("JOIN_ROOM",room_id=room["id"]); c.until("ROOM_STATE")
            host.send("START_GAME")
            def worker(index,c):
                seq=0
                try:
                    while not stop.is_set():
                        state=c.until("WORLD_STATE",2)
                        sizes.append(len(encode_packet(state)))
                        tick_count[index]+=1
                        me=next(s for s in state["snakes"] if s["id"]==str(c.auth["user"]["id"]))
                        if not me["alive"]:
                            c.send("RESPAWN")
                        else:
                            x,y=me["body"][0]
                            # Circle around centre; server still owns physics/collisions.
                            target=math.atan2(1500-y,1500-x)+.55
                            seq+=1; c.send("PLAYER_INPUT",angle=target,boost=False,seq=seq)
                except Exception as exc:
                    if not stop.is_set(): failures.append(str(exc))
            for i,c in enumerate(clients):
                t=threading.Thread(target=worker,args=(i,c),daemon=True); t.start(); workers.append(t)
            start=time.monotonic()
            while time.monotonic()-start<args.seconds:
                samples.append(server.tick_ms); time.sleep(.05)
            elapsed=time.monotonic()-start
            stop.set()
            for t in workers: t.join(3)
            ordered=sorted(samples)
            result={"platform":platform.platform(),"python":platform.python_version(),"clients":8,"bots":4,
                    "transport":"TCP localhost","database":"SQLite","duration_seconds":round(elapsed,2),
                    "configured_physics_hz":30,"configured_snapshot_hz":15,
                    "tick_ms_median":round(statistics.median(samples),3),
                    "tick_ms_p95":round(ordered[int((len(ordered)-1)*.95)],3),
                    "snapshot_bytes_mean":round(statistics.mean(sizes)),
                    "received_snapshots":tick_count,"worker_errors":failures}
            path=Path(args.out); path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if failures: raise SystemExit(1)
        finally:
            stop.set()
            for c in clients: c.close()
            server.shutdown(); runner.join(3)


if __name__=="__main__": main()
