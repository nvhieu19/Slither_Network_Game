from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from server.database import Database,verify_password


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database(path=Path(self.tmp.name)/"test.db")
        self.user=self.db.register("player_one","password123","Người chơi")
    def tearDown(self): self.tmp.cleanup()

    def test_password_salted_and_valid_login(self):
        self.db.register("player_two","password123","Hai")
        with self.db.cursor() as cur:
            cur.execute("SELECT password_hash FROM users ORDER BY id")
            hashes=[r["password_hash"] for r in cur.fetchall()]
        self.assertNotEqual(hashes[0],hashes[1])
        self.assertNotIn("password123",hashes[0])
        self.assertTrue(verify_password("password123",hashes[0]))
        self.assertEqual(self.db.login("PLAYER_ONE","password123")["id"],self.user["id"])
        with self.assertRaises(ValueError): self.db.login("player_one","wrong")

    def test_password_verification_rejects_malformed_values(self):
        self.assertFalse(verify_password(None, "malformed"))
        self.assertFalse(verify_password("password123", None))
        self.assertFalse(verify_password("password123", "malformed"))

    def test_duplicate_and_validation(self):
        for username,password in [("player_one","password123"),("bad' OR 1=1","password123"),("ok_name","short")]:
            with self.assertRaises(ValueError): self.db.register(username,password,"Name")

    def test_profile_rejects_invalid_name_and_skin(self):
        for name in (None, "", "x" * 21):
            with self.assertRaises(ValueError):
                self.db.update_profile(self.user["id"], name, "#B395FF")
        with self.assertRaises(ValueError):
            self.db.update_profile(self.user["id"], "Tên mới", "invalid")
        self.assertEqual(self.db.profile(self.user["id"])["display_name"], "Người chơi")

    @patch("server.database.sqlite3.connect")
    def test_cursor_closes_connection_if_setup_fails(self, connect):
        connection = connect.return_value
        connection.execute.side_effect = RuntimeError("setup failed")
        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            with self.db.cursor():
                pass
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()

    @patch("server.database.sqlite3.connect")
    def test_cursor_closes_connection_if_cursor_close_fails(self, connect):
        connection = connect.return_value
        connection.cursor.return_value.close.side_effect = RuntimeError("cursor close failed")
        with self.assertRaisesRegex(RuntimeError, "cursor close failed"):
            with self.db.cursor():
                pass
        connection.close.assert_called_once()

    def test_match_idempotency_and_peak_score(self):
        self.db.create_room("room12345678","Room",self.user["id"],8)
        event={"run_id":"a"*32,"score":30,"final_score":20,"max_length":33,"duration":10.5,"reason":"wall"}
        self.db.save_match(self.user["id"],"room12345678",event)
        self.db.save_match(self.user["id"],"room12345678",event)
        self.assertEqual(len(self.db.history(self.user["id"])),1)
        self.assertEqual(self.db.profile(self.user["id"])["highest_score"],30)
        event={**event,"run_id":"b"*32,"score":10}
        self.db.save_match(self.user["id"],"room12345678",event)
        self.assertEqual(self.db.profile(self.user["id"])["highest_score"],30)

    def test_profile_persistence(self):
        self.db.update_profile(self.user["id"],"Tên mới","#B395FF")
        again=Database(path=Path(self.tmp.name)/"test.db")
        user=again.login("player_one","password123")
        self.assertEqual(user["display_name"],"Tên mới")
        self.assertEqual(user["skin_color"],"#B395FF")
