"""Repository: MySQL connection pool in deployment, SQLite for zero-setup demos.

Only the server imports this module; clients never receive DB credentials.
SQL parameters are always bound. Passwords use salted PBKDF2-HMAC-SHA256.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from common.config import SKINS

ITERATIONS = 210000


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, encoded):
    try:
        scheme, count, salt, expected = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count)).hex()
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def clean_text(value, maximum):
    if not isinstance(value, str):
        raise ValueError("Nội dung phải là văn bản.")
    value = " ".join(value.split())
    if not value or len(value) > maximum or not all(c.isprintable() for c in value):
        raise ValueError(f"Nội dung cần từ 1 đến {maximum} ký tự.")
    return value


class Database:
    def __init__(self, mode="sqlite", path="data/slither.db"):
        self.mode, self.path = mode, str(path)
        self.pool = None
        if mode == "mysql":
            from mysql.connector.pooling import MySQLConnectionPool
            self.pool = MySQLConnectionPool(
                pool_name="slither_pool_"+secrets.token_hex(3), pool_size=8,
                host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "slither_app"), password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "slither_network"),
                charset="utf8mb4", autocommit=False, connection_timeout=5)
            with self.cursor() as cur:
                cur.execute("SELECT id FROM users LIMIT 1")
                cur.fetchall()
        elif mode == "sqlite":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        else:
            raise ValueError("Unknown database mode")

    @contextmanager
    def cursor(self):
        conn = self.pool.get_connection() if self.pool else sqlite3.connect(self.path, timeout=10)
        if not self.pool:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor(dictionary=True) if self.pool else conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def sql(self, query):
        return query.replace("?", "%s") if self.pool else query

    def _init_sqlite(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
              skin_color TEXT NOT NULL DEFAULT '#54E8B0', highest_score INTEGER NOT NULL DEFAULT 0,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS rooms (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, owner_id INTEGER NOT NULL REFERENCES users(id),
              capacity INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'WAITING',
              created_at TEXT DEFAULT CURRENT_TIMESTAMP, closed_at TEXT);
            CREATE TABLE IF NOT EXISTS match_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
              user_id INTEGER NOT NULL REFERENCES users(id), room_id TEXT NOT NULL REFERENCES rooms(id),
              score INTEGER NOT NULL, final_score INTEGER NOT NULL, max_length INTEGER NOT NULL,
              duration_seconds REAL NOT NULL, death_reason TEXT NOT NULL,
              played_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_score ON users(highest_score);
            CREATE INDEX IF NOT EXISTS idx_history_user ON match_history(user_id, played_at);
            """)

    @staticmethod
    def public(row):
        return {key: row[key] for key in ("id", "username", "display_name", "skin_color", "highest_score")}

    def register(self, username, password, display_name):
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
            raise ValueError("Tài khoản gồm 3–24 chữ cái, số hoặc dấu gạch dưới.")
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ValueError("Mật khẩu cần từ 8 đến 128 ký tự.")
        name = clean_text(display_name, 20)
        username = username.lower()
        encoded = hash_password(password)
        with self.cursor() as cur:
            cur.execute(self.sql("SELECT id FROM users WHERE username=?"), (username,))
            if cur.fetchone():
                raise ValueError("Tên tài khoản đã được sử dụng.")
            try:
                cur.execute(self.sql("INSERT INTO users(username,display_name,password_hash) VALUES(?,?,?)"),
                            (username, name, encoded))
            except Exception as exc:
                if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                    raise ValueError("Tên tài khoản đã được sử dụng.") from exc
                raise
        return self.login(username, password)

    def login(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 128:
            raise ValueError("Sai tài khoản hoặc mật khẩu.")
        with self.cursor() as cur:
            cur.execute(self.sql("SELECT * FROM users WHERE username=?"), (username.lower(),))
            row = cur.fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise ValueError("Sai tài khoản hoặc mật khẩu.")
        return self.public(row)

    def profile(self, uid):
        with self.cursor() as cur:
            cur.execute(self.sql("SELECT * FROM users WHERE id=?"), (uid,))
            row = cur.fetchone()
            return self.public(row) if row else None

    def update_profile(self, uid, name, skin):
        name = clean_text(name, 20)
        if skin not in SKINS:
            raise ValueError("Màu không nằm trong bảng skin.")
        with self.cursor() as cur:
            cur.execute(self.sql("UPDATE users SET display_name=?, skin_color=? WHERE id=?"), (name, skin, uid))
        return self.profile(uid)

    def create_room(self, rid, name, owner, capacity):
        with self.cursor() as cur:
            cur.execute(self.sql("INSERT INTO rooms(id,name,owner_id,capacity,status) VALUES(?,?,?,?,'WAITING')"),
                        (rid, name, owner, capacity))

    def room_status(self, rid, status):
        with self.cursor() as cur:
            cur.execute(self.sql("UPDATE rooms SET status=?, closed_at=CASE WHEN ?='CLOSED' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?"),
                        (status, status, rid))

    def close_old_rooms(self):
        with self.cursor() as cur:
            cur.execute("UPDATE rooms SET status='CLOSED', closed_at=CURRENT_TIMESTAMP WHERE status <> 'CLOSED'")

    def save_match(self, uid, rid, event):
        with self.cursor() as cur:
            # UNIQUE run_id plus INSERT IGNORE makes retries idempotent.
            prefix = "INSERT IGNORE" if self.pool else "INSERT OR IGNORE"
            cur.execute(self.sql(prefix + " INTO match_history(run_id,user_id,room_id,score,final_score,max_length,duration_seconds,death_reason) VALUES(?,?,?,?,?,?,?,?)"),
                        (event["run_id"], uid, rid, event["score"], event["final_score"],
                         event["max_length"], event["duration"], event["reason"]))
            cur.execute(self.sql("UPDATE users SET highest_score=CASE WHEN highest_score < ? THEN ? ELSE highest_score END WHERE id=?"),
                        (event["score"], event["score"], uid))

    def leaderboard(self):
        with self.cursor() as cur:
            cur.execute("SELECT display_name,highest_score,skin_color FROM users ORDER BY highest_score DESC,username ASC LIMIT 50")
            return [dict(row) for row in cur.fetchall()]

    def history(self, uid):
        with self.cursor() as cur:
            cur.execute(self.sql("SELECT score,final_score,max_length,duration_seconds,death_reason,played_at FROM match_history WHERE user_id=? ORDER BY id DESC LIMIT 20"), (uid,))
            return [{**dict(r), "duration_seconds": float(r["duration_seconds"]), "played_at": str(r["played_at"])} for r in cur.fetchall()]
