"""Scenario 1: IAM audit for a ~120-person company (acme.example). All data is fake.

Tables
    departments(id, name, cost_center)
    employees(id, upn, display_name, department_id, manager_id, title, user_type,
              country, hire_date, termination_date, account_enabled)
    groups(id, name, kind, created)
    group_members(group_id, member_type, member_id, added_on)   member_type: user | group
    apps(id, name, sensitivity, owner_id)
    app_assignments(app_id, principal_type, principal_id, role, assigned_on)
    sign_ins(id, ts, user_id, app_id, ip, country, result, failure_reason, mfa, client)
    role_activations(id, user_id, role, activated_at, expires_at, justification)   (PIM-style)

Planted incidents (the hard problems find these - don't read this before solving!):
    brute force, password spray, impossible travel, leaver still signing in,
    guest reaching a high-sensitivity app through nested groups, overlapping PIM activations.

Fake-data rules: emails use reserved .example domains; IPs only from RFC 5737
documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24).
"""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from datagen.fakes import FIRST_NAMES, LAST_NAMES

LOG_START = datetime(2026, 10, 15)
LOG_DAYS = 30                       # logs cover 2026-10-15 .. 2026-11-13
OFFICE_IP = {"US": "198.51.100.", "DE": "203.0.113.", "GB": "203.0.113."}
ATTACKER_IP = "192.0.2."

SCHEMA = """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, cost_center TEXT);
CREATE TABLE employees (
  id INTEGER PRIMARY KEY, upn TEXT UNIQUE NOT NULL, display_name TEXT,
  department_id INTEGER REFERENCES departments(id), manager_id INTEGER REFERENCES employees(id),
  title TEXT, user_type TEXT CHECK (user_type IN ('member','guest')), country TEXT,
  hire_date TEXT, termination_date TEXT, account_enabled INTEGER NOT NULL);
CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, kind TEXT, created TEXT);
CREATE TABLE group_members (
  group_id INTEGER REFERENCES groups(id), member_type TEXT CHECK (member_type IN ('user','group')),
  member_id INTEGER NOT NULL, added_on TEXT, PRIMARY KEY (group_id, member_type, member_id));
CREATE TABLE apps (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  sensitivity TEXT CHECK (sensitivity IN ('low','medium','high')), owner_id INTEGER REFERENCES employees(id));
CREATE TABLE app_assignments (
  app_id INTEGER REFERENCES apps(id), principal_type TEXT CHECK (principal_type IN ('user','group')),
  principal_id INTEGER NOT NULL, role TEXT, assigned_on TEXT,
  PRIMARY KEY (app_id, principal_type, principal_id));
CREATE TABLE sign_ins (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, user_id INTEGER REFERENCES employees(id),
  app_id INTEGER REFERENCES apps(id), ip TEXT, country TEXT,
  result TEXT CHECK (result IN ('success','failure')), failure_reason TEXT,
  mfa INTEGER, client TEXT CHECK (client IN ('browser','mobile','legacy')));
CREATE TABLE role_activations (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES employees(id),
  role TEXT, activated_at TEXT, expires_at TEXT, justification TEXT);
CREATE INDEX ix_signin_user_ts ON sign_ins(user_id, ts);
CREATE INDEX ix_signin_ip ON sign_ins(ip);
"""

DEPTS = [("Engineering", "CC-100", "US"), ("Sales", "CC-200", "US"), ("Finance", "CC-300", "US"),
         ("HR", "CC-400", "GB"), ("IT", "CC-500", "US"), ("Marketing", "CC-600", "DE"),
         ("Legal", "CC-700", "GB"), ("Support", "CC-800", "DE"), ("Research", "CC-900", "US")]
# Research has no employees on purpose (LEFT JOIN lesson).

def _people(rng: random.Random) -> list[dict]:
    """Org chart: CEO -> 8 dept heads -> 2 managers each -> 4-7 ICs each (depth 4), plus guests."""
    people: list[dict] = []

    def add(dept_id, manager_id, title, country, user_type="member", domain="acme.example"):
        pid = len(people) + 1
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        if user_type == "guest":
            upn = f"{first.lower()}.{last.lower()}_{domain}#EXT#@acme.example"
        else:
            upn = f"{first.lower()}.{last.lower()}{pid}@acme.example"
        hire = (datetime(2018, 1, 1) + timedelta(days=rng.randint(0, 3000))).date().isoformat()
        people.append(dict(id=pid, upn=upn, display_name=f"{first} {last}", department_id=dept_id,
                           manager_id=manager_id, title=title, user_type=user_type, country=country,
                           hire_date=hire, termination_date=None, account_enabled=1))
        return pid

    ceo = add(None, None, "CEO", "US")
    for d_id, (name, _, country) in enumerate(DEPTS[:-1], start=1):
        head = add(d_id, ceo, f"VP {name}", country)
        for _ in range(2):
            mgr = add(d_id, head, f"{name} Manager", country)
            for _ in range(rng.randint(4, 7)):
                add(d_id, mgr, f"{name} Specialist", country)
    for dom in ["partner.example"] * 5 + ["vendor.example"] * 3:
        add(None, None, "Guest", "US", "guest", dom)

    # Leavers: 6 terminated ICs. The JML process failed for 2 of them (still enabled).
    ics = [p for p in people if p["title"].endswith("Specialist")]
    for i, p in enumerate(rng.sample(ics, 6)):
        p["termination_date"] = (datetime(2026, 9, 20) + timedelta(days=7 * i)).date().isoformat()
        p["account_enabled"] = 1 if i in (3, 4) else 0
    return people


# Groups: (name, kind, user members selector, nested group names)
def _groups(people: list[dict]) -> list[tuple]:
    by_dept = lambda d: [p["id"] for p in people if p["department_id"] == d]  # noqa: E731
    guests = [p["id"] for p in people if p["user_type"] == "guest"]
    managers = [p["id"] for p in people if "Manager" in p["title"] or p["title"].startswith("VP")]
    it = by_dept(5)
    return [
        *[(f"{n} Team", "security", by_dept(i), []) for i, (n, _, _) in enumerate(DEPTS[:-1], start=1)],
        ("All Staff", "dynamic", [1], [f"{n} Team" for n, _, _ in DEPTS[:-1]]),
        ("Managers", "security", managers, []),
        ("Contractors", "security", guests[:3], []),
        ("Helpdesk", "security", it[3:6], ["Contractors"]),        # guests nested in helpdesk...
        ("IT Admins", "security", it[:3], ["Helpdesk"]),           # ...nested in IT admins
        ("Finance Approvers", "security", by_dept(3)[:4], []),
        ("Partner Portal Users", "m365", guests, []),
        ("Research Team", "security", [], []),                     # empty group
    ]


# Apps: (name, sensitivity, assigned groups, assigned direct users by index-in-people)
APPS = [
    ("Wiki", "low", ["All Staff"]), ("Chat", "low", ["All Staff", "Partner Portal Users"]),
    ("Email", "medium", ["All Staff"]), ("CRM", "medium", ["Sales Team", "Support Team"]),
    ("SourceRepo", "high", ["Engineering Team", "Contractors"]), ("BuildCI", "medium", ["Engineering Team"]),
    ("PayrollHub", "high", ["HR Team", "Finance Approvers"]), ("LedgerERP", "high", ["Finance Team"]),
    ("AdminConsole", "high", ["IT Admins"]), ("TicketDesk", "medium", ["Support Team", "Helpdesk"]),
    ("ContractVault", "high", ["Legal Team"]), ("AdsManager", "medium", ["Marketing Team"]),
    ("LegacyFTP", "high", []),   # no assignments: orphan app
]


def build(path: Path, seed: int = 2026) -> Path:
    rng = random.Random(seed)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    people = _people(rng)
    con.executemany("INSERT INTO departments VALUES (?,?,?)",
                    [(i, n, cc) for i, (n, cc, _) in enumerate(DEPTS, start=1)])
    cols = list(people[0])
    con.executemany(f"INSERT INTO employees ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [tuple(p[c] for c in cols) for p in people])

    groups = _groups(people)
    gid = {name: i for i, (name, *_) in enumerate(groups, start=1)}
    con.executemany("INSERT INTO groups VALUES (?,?,?,?)",
                    [(gid[n], n, k, f"2024-0{1 + i % 9}-15") for i, (n, k, _, _) in enumerate(groups)])
    for name, _, users, nested in groups:
        con.executemany("INSERT INTO group_members VALUES (?,?,?,?)",
                        [(gid[name], "user", u, "2025-02-01") for u in users]
                        + [(gid[name], "group", gid[n], "2025-02-01") for n in nested])

    ids = {p["id"]: p for p in people}
    owners = [p["id"] for p in people if "Manager" in p["title"]]
    con.executemany("INSERT INTO apps VALUES (?,?,?,?)",
                    [(i, n, s, rng.choice(owners)) for i, (n, s, _) in enumerate(APPS, start=1)])
    for app_id, (_, _, gnames) in enumerate(APPS, start=1):
        con.executemany("INSERT INTO app_assignments VALUES (?,?,?,?,?)",
                        [(app_id, "group", gid[g], "user", "2025-03-01") for g in gnames])
    leavers = [p for p in people if p["termination_date"] and not p["account_enabled"]]
    marketer = next(p for p in people if p["department_id"] == 6 and p["title"].endswith("Specialist"))
    con.executemany("INSERT INTO app_assignments VALUES (?,?,?,?,?)", [
        (9, "user", leavers[0]["id"], "admin", "2024-06-01"),     # disabled leaver, still admin
        (7, "user", marketer["id"], "user", "2026-08-12"),         # odd: marketing in payroll
    ])

    _sign_ins(con, rng, people, ids)
    _pim(con, rng, people)
    con.commit()
    con.close()
    return path


def _ip(rng, country):
    return OFFICE_IP[country] + str(rng.randint(1, 120) + (128 if country == "GB" else 0))


def _sign_ins(con, rng, people, ids) -> None:
    rows = []

    def log(ts, uid, app, ip, country, ok=True, mfa=1, client="browser"):
        rows.append((ts.strftime("%Y-%m-%d %H:%M:%S"), uid, app, ip, country,
                     "success" if ok else "failure", None if ok else "invalid_password",
                     mfa if ok else 0, client))

    members = [p for p in people if p["user_type"] == "member"]
    mfa_exempt = {p["id"] for p in rng.sample(members, 9)}     # MFA coverage gaps
    for day in range(LOG_DAYS):
        d = LOG_START + timedelta(days=day)
        weekend = d.weekday() >= 5
        for p in members:
            if p["termination_date"] and p["termination_date"] <= d.date().isoformat():
                continue
            if weekend and rng.random() > 0.1:
                continue
            for _ in range(rng.randint(1, 4)):
                ts = d + timedelta(hours=rng.randint(7, 18), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
                client = rng.choices(["browser", "mobile", "legacy"], [78, 20, 2])[0]
                ok = rng.random() > 0.04
                mfa = 0 if client == "legacy" or p["id"] in mfa_exempt else 1
                log(ts, p["id"], rng.randint(1, 12), _ip(rng, p["country"]), p["country"], ok, mfa, client)
    for g in [p for p in people if p["user_type"] == "guest"][:5]:  # last 3 guests never sign in
        for day in range(0, LOG_DAYS, rng.randint(3, 6)):
            log(LOG_START + timedelta(days=day, hours=15), g["id"], rng.choice([2, 5]), _ip(rng, "US"), "US")

    eng = [p for p in members if p["department_id"] == 1 and not p["termination_date"]]
    sales = [p for p in members if p["department_id"] == 2 and not p["termination_date"]]
    # 1) Brute force: 25 failures in ~8 minutes, then a success over legacy auth (no MFA).
    victim, t = eng[3], datetime(2026, 11, 3, 2, 10)
    for i in range(25):
        log(t + timedelta(seconds=20 * i), victim["id"], 3, ATTACKER_IP + "50", "NL", ok=False, client="legacy")
    log(t + timedelta(seconds=550), victim["id"], 3, ATTACKER_IP + "50", "NL", mfa=0, client="legacy")
    # 2) Password spray: one IP, one failure each against 30 different users.
    for i, p in enumerate(rng.sample([m for m in members if not m["termination_date"]], 30)):
        log(datetime(2026, 11, 7, 3, 0) + timedelta(seconds=70 * i), p["id"], 3, ATTACKER_IP + "77", "NL", ok=False)
    # 3) Impossible travel (US -> DE in 48 minutes) and a legitimate trip (2 days apart).
    log(datetime(2026, 11, 5, 9, 0), sales[2]["id"], 4, _ip(rng, "US"), "US")
    log(datetime(2026, 11, 5, 9, 48), sales[2]["id"], 4, "203.0.113.200", "DE")
    log(datetime(2026, 11, 1, 10, 0), sales[4]["id"], 4, _ip(rng, "US"), "US")
    log(datetime(2026, 11, 3, 14, 0), sales[4]["id"], 4, "203.0.113.201", "DE")
    # 4) Leaver whose account was never disabled keeps signing in.
    ghost = [p for p in people if p["termination_date"] and p["account_enabled"]][0]
    for ts in (datetime(2026, 10, 28, 22, 15), datetime(2026, 11, 10, 23, 40)):
        log(ts, ghost["id"], 7, _ip(rng, ghost["country"]), ghost["country"], mfa=0)

    rows.sort()
    con.executemany("INSERT INTO sign_ins (ts,user_id,app_id,ip,country,result,failure_reason,mfa,client)"
                    " VALUES (?,?,?,?,?,?,?,?,?)", rows)


def _pim(con, rng, people) -> None:
    roles = ["Global Administrator", "User Administrator", "Exchange Administrator", "Billing Administrator"]
    admins = [p["id"] for p in people if p["department_id"] == 5][:6]
    reasons = ["INC-4412 mailbox restore", "CHG-0931 license update", "quarterly access review",
               "onboarding batch", "", "", "fix"]
    rows = []
    for _ in range(40):
        start = LOG_START + timedelta(days=rng.randint(0, LOG_DAYS - 1), hours=rng.randint(8, 17))
        rows.append((rng.choice(admins), rng.choice(roles), start, start + timedelta(hours=rng.randint(1, 8)),
                     rng.choice(reasons)))
    s = datetime(2026, 11, 9, 9)  # planted overlap: same admin, same role, activated twice
    rows += [(admins[0], "Global Administrator", s, s + timedelta(hours=8), "fix"),
             (admins[0], "Global Administrator", s + timedelta(hours=3), s + timedelta(hours=11), "")]
    rows.sort(key=lambda r: r[2])
    fmt = "%Y-%m-%d %H:%M:%S"
    con.executemany("INSERT INTO role_activations (user_id,role,activated_at,expires_at,justification)"
                    " VALUES (?,?,?,?,?)", [(u, r, a.strftime(fmt), e.strftime(fmt), j) for u, r, a, e, j in rows])
