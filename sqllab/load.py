"""Turn permissions.json + manifest.json into a SQLite database you can query.

    python -m sqllab.load            # writes lab_data/lab.db
    sqlite3 lab_data/lab.db          # then type SQL

Tables (all data is fake):
    users(id, upn, display_name, department, type, enabled, last_sign_in)
    groups(id, name)
    group_members(group_id, member_id)         member_id may itself be a group (nesting!)
    files(path, container, owner, inherit, last_modified, last_accessed, sensitive,
          ssn, credit_card, email, health_record, note)
    grants(path, principal, principal_kind, principal_ref, role, created, expires, created_by)
          path is a container ("finance") or a file ("finance/payments/x.csv")
"""

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE users (id TEXT PRIMARY KEY, upn TEXT, display_name TEXT, department TEXT,
                    type TEXT, enabled INTEGER, last_sign_in TEXT);
CREATE TABLE groups (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE group_members (group_id TEXT REFERENCES groups(id), member_id TEXT);
CREATE TABLE files (path TEXT PRIMARY KEY, container TEXT, owner TEXT REFERENCES users(id),
                    inherit INTEGER, last_modified TEXT, last_accessed TEXT, sensitive INTEGER,
                    ssn INTEGER, credit_card INTEGER, email INTEGER, health_record INTEGER, note TEXT);
CREATE TABLE grants (path TEXT, principal TEXT, principal_kind TEXT, principal_ref TEXT,
                     role TEXT, created TEXT, expires TEXT, created_by TEXT);
"""


def load(lab: Path) -> Path:
    perms = json.loads((lab / "permissions.json").read_text())
    manifest = json.loads((lab / "manifest.json").read_text())
    db = lab / "lab.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                    [(u["id"], u["upn"], u["display_name"], u["department"], u["type"],
                      int(u["enabled"]), u["last_sign_in"]) for u in perms["users"]])
    con.executemany("INSERT INTO groups VALUES (?,?)", [(g["id"], g["name"]) for g in perms["groups"]])
    con.executemany("INSERT INTO group_members VALUES (?,?)",
                    [(g["id"], m) for g in perms["groups"] for m in g["members"]])
    for path, acl in perms["acls"].items():
        meta = manifest["files"].get(path)
        if meta:  # a file, not a container
            t = meta["truth"]
            con.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                path, path.split("/")[0], acl["owner"], int(acl["inherit"]), acl["last_modified"],
                acl["last_accessed"], int(meta["sensitive"]), t.get("ssn", 0), t.get("credit_card", 0),
                t.get("email", 0), t.get("health_record", 0), meta["note"]))
        for g in acl["grants"]:
            kind, _, ref = g["principal"].partition(":")
            con.execute("INSERT INTO grants VALUES (?,?,?,?,?,?,?,?)", (
                path, g["principal"], kind, ref or None, g["role"], g["created"],
                g.get("expires"), g.get("created_by")))
    con.commit()
    con.close()
    return db


if __name__ == "__main__":
    import sys
    print(f"wrote {load(Path(sys.argv[1] if len(sys.argv) > 1 else 'lab_data'))}")
