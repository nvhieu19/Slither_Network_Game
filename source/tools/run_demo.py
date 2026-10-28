"""Start an isolated SQLite demo server and one/two real client processes."""
from pathlib import Path
import argparse
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.database import Database


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--clients",type=int,choices=[1,2],default=1)
    parser.add_argument("--port",type=int,default=5555)
    args=parser.parse_args()
    probe=socket.socket()
    try:
        probe.bind(("127.0.0.1",args.port))
    except OSError:
        print(f"Port {args.port} is in use. Close the running server or add --port 5556.")
        return 1
    finally:
        probe.close()
    path=ROOT/"data"/"demo.db"
    db=Database(path=path)
    names=[("demo_one","Pilot One"),("demo_two","Pilot Two")]
    for username,name in names:
        try: db.register(username,"SlitherDemo2026",name)
        except ValueError: pass
    log=open(ROOT/"data"/"demo_console.log","a",encoding="utf-8")
    server=subprocess.Popen([sys.executable,"-m","server","--database","sqlite","--db-path",str(path),"--port",str(args.port)],cwd=ROOT,stdout=log,stderr=log)
    clients=[]
    try:
        ready=False
        for _ in range(40):
            if server.poll() is not None: break
            try:
                with socket.create_connection(("127.0.0.1",args.port),.2): pass
                ready=True; break
            except OSError: time.sleep(.1)
        if not ready:
            print("Server did not start. See data/demo_console.log."); return 1
        for username,_ in names[:args.clients]:
            clients.append(subprocess.Popen([sys.executable,"-m","client","--port",str(args.port),"--username",username,"--password","SlitherDemo2026"],cwd=ROOT))
        print("Demo ready. Create a room, join with the other window, then click START.")
        print("Close both client windows to stop the demo server. Ctrl+C also stops everything.")
        while any(p.poll() is None for p in clients): time.sleep(.3)
    except KeyboardInterrupt:
        pass
    finally:
        for p in clients:
            if p.poll() is None: p.terminate()
        # A graceful server stop is preferable to terminate: SIGINT is unavailable
        # cross-platform, so wait for disconnected matches to finish writing first.
        time.sleep(.6)
        server.terminate()
        try: server.wait(timeout=3)
        except subprocess.TimeoutExpired: server.kill()
        log.close()
    return 0


if __name__=="__main__": raise SystemExit(main())
