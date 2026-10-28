"""Opt-in MySQL smoke check. Writes one clearly named QA account and room.

Uses .env. The created QA rows remain available for inspection in Workbench.
Run against a development database, not an unrelated production schema.
"""
import secrets
from server.__main__ import load_env
from server.database import Database


def main():
    load_env()
    db=Database("mysql")
    tag=secrets.token_hex(5)
    user=db.register("qa_"+tag,"QA_"+secrets.token_urlsafe(18),"Kiểm thử MySQL")
    rid=secrets.token_hex(6)
    db.create_room(rid,"Phòng kiểm thử MySQL",user["id"],8)
    event={"run_id":secrets.token_hex(16),"score":25,"final_score":19,"max_length":30,"duration":12.5,"reason":"qa_check"}
    db.save_match(user["id"],rid,event)
    db.save_match(user["id"],rid,event)
    assert db.profile(user["id"])["highest_score"]==25
    assert len(db.history(user["id"]))==1
    db.room_status(rid,"CLOSED")
    print("MYSQL PASS: pool, register, FK, transaction, history, idempotency, peak score.")
    print("QA rows retained for review; username:",user["username"],"room:",rid)


if __name__=="__main__": main()
