import argparse
import json
import logging
import os
from pathlib import Path
import threading
from server.database import Database
from server.app import GameServer

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Neon Slither authoritative TCP server")
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SERVER_PORT", "5555")))
    parser.add_argument("--database", choices=["sqlite", "mysql"], default=os.getenv("DATABASE_MODE", "sqlite"))
    parser.add_argument("--db-path", default=str(ROOT/"data"/"slither.db"))
    parser.add_argument("--console", action="store_true", help="Enable status / kick USER / stop commands")
    args = parser.parse_args()
    (ROOT/"data").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT/"data"/"server.log", encoding="utf-8")])
    try:
        db = Database(args.database, args.db_path)
        server = GameServer(db, args.host, args.port)
    except Exception as exc:
        logging.error("Cannot open database: %s. For MySQL, import ../database/schema_mysql.sql and check .env.", exc)
        return 1

    def console():
        while not server.stop_event.is_set():
            try:
                command = input().strip()
            except (EOFError, OSError):
                return
            if command in ("status", "rooms"):
                print(json.dumps(server.status(), ensure_ascii=False, indent=2))
            elif command.startswith("kick "):
                print("Disconnected" if server.kick_username(command[5:]) else "User not found")
            elif command == "stop":
                server.shutdown()
                return
            else:
                print("Commands: status | rooms | kick USERNAME | stop")
    if args.console:
        threading.Thread(target=console, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    except OSError as exc:
        logging.error("Cannot listen: %s", exc)
        server.shutdown()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
