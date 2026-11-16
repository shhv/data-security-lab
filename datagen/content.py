"""File content builders.

Each builder returns (text, truth) where `truth` counts what was ACTUALLY planted:
    ssn, credit_card, email, health_record  -> true sensitive values
    decoy_ssn, decoy_card                   -> look-alikes that should NOT be flagged

Why keep ground truth? Without labels you can't measure a classifier. Stage 2 compares
detections against this manifest to compute precision (how many hits were real) and
recall (how many real items were found) - the two numbers every DLP tuning debate is about.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter

from .fakes import PARTNER_DOMAIN, PERSONAL_DOMAIN, Faker

Built = tuple[str, Counter]


def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def hr_roster(fk: Faker, n: int = 20) -> Built:
    t = Counter()
    rows = [["employee_name", "work_email", "department", "ssn", "date_of_birth"]]
    for _ in range(n):
        first, last = fk.name()
        rows.append([f"{first} {last}", fk.email(first, last), fk.rng.choice(["Sales", "Ops", "IT"]),
                     fk.ssn(fk.rng.choice(["dashed", "spaced"])), fk.dob()])
        t["ssn"] += 1
        t["email"] += 1
    return _csv(rows), t


def payroll(fk: Faker, n: int = 15) -> Built:
    """SSNs stored as bare 9 digits under a cryptic header - regex alone will struggle."""
    t = Counter()
    rows = [["emp_id", "full_name", "tin", "gross_pay"]]
    for i in range(n):
        first, last = fk.name()
        rows.append([f"E{1000 + i}", f"{first} {last}", fk.ssn("bare"), fk.rng.randint(3000, 12000)])
        t["ssn"] += 1
    return _csv(rows), t


def transactions(fk: Faker, n: int = 25) -> Built:
    t = Counter()
    rows = [["txn_id", "order_id", "card_brand", "card_number", "amount", "customer_email"]]
    for i in range(n):
        first, last = fk.name()
        brand, pan = fk.card(fk.rng.choice(["plain", "spaced", "dashed"]))
        rows.append([f"T{50000 + i}", fk.order_id(), brand, pan,
                     f"{fk.rng.uniform(5, 900):.2f}", fk.email(first, last, "example.com")])
        t["credit_card"] += 1
        t["email"] += 1
        t["decoy_ssn"] += 1  # the 9-digit order_id
    return _csv(rows), t


def invoice_numbers(fk: Faker, n: int = 12) -> Built:
    """16-digit invoice IDs that look like Visa numbers but fail Luhn."""
    t = Counter()
    lines = ["Invoice reference list (internal)", ""]
    for _ in range(n):
        lines.append(f"INV {fk.decoy_card_like()}  status=paid")
        t["decoy_card"] += 1
    return "\n".join(lines) + "\n", t


def support_ticket(fk: Faker, ticket_no: int, with_card: bool) -> Built:
    t = Counter()
    first, last = fk.name()
    email = fk.email(first, last, PERSONAL_DOMAIN)
    t["email"] += 1
    body = [f"Ticket #{ticket_no}", f"From: {first} {last} <{email}>",
            f"Phone: {fk.phone()}", ""]
    if with_card:
        _, pan = fk.card("spaced")
        body.append(f"Hi, my payment failed. My card number is {pan}, exp 12/29. Please retry.")
        t["credit_card"] += 1
    else:
        body.append(f"Hi, where is my order {fk.order_id()}? It's been two weeks.")
        t["decoy_ssn"] += 1
    return "\n".join(body) + "\n", t


def newsletter_list(fk: Faker, n: int = 40) -> Built:
    t = Counter()
    rows = [["email", "opted_in"]]
    for _ in range(n):
        first, last = fk.name()
        rows.append([fk.email(first, last, "example.org"), "yes"])
        t["email"] += 1
    return _csv(rows), t


def app_log(fk: Faker, n: int = 30) -> Built:
    """Logs leak PII constantly (emails in auth lines, IDs everywhere)."""
    t = Counter()
    lines = []
    for i in range(n):
        ts = f"2026-11-{fk.rng.randint(1, 13):02d}T{fk.rng.randint(0, 23):02d}:{i % 60:02d}:00Z"
        if i % 3 == 0:
            first, last = fk.name()
            lines.append(f"{ts} INFO auth login ok user={fk.email(first, last)}")
            t["email"] += 1
        elif i % 7 == 0:
            lines.append(f"{ts} WARN validation rejected ssn_field={fk.decoy_ssn_like()}")
            t["decoy_ssn"] += 1
        else:
            lines.append(f"{ts} INFO GET /api/orders/{fk.order_id()} 200")
            t["decoy_ssn"] += 1
    return "\n".join(lines) + "\n", t


def patient_records(fk: Faker, n: int = 10) -> Built:
    """Health data: no single regex identifies it. It's the COMBINATION
    (name + DOB + MRN + diagnosis) that makes it PHI."""
    t = Counter()
    recs = []
    for _ in range(n):
        first, last = fk.name()
        code, desc = fk.diagnosis()
        rec = {"patient": f"{first} {last}", "dob": fk.dob(), "mrn": fk.mrn(),
               "diagnosis_code": code, "diagnosis": desc}
        if fk.rng.random() < 0.5:
            rec["ssn"] = fk.ssn()
            t["ssn"] += 1
        recs.append(rec)
        t["health_record"] += 1
    return json.dumps(recs, indent=2) + "\n", t


def partner_export(fk: Faker, n: int = 8) -> Built:
    t = Counter()
    rows = [["mrn", "diagnosis_code", "referring_contact"]]
    for _ in range(n):
        first, last = fk.name()
        rows.append([fk.mrn(), fk.diagnosis()[0], fk.email(first, last, PARTNER_DOMAIN)])
        t["health_record"] += 1
        t["email"] += 1
    return _csv(rows), t


def dev_notes(fk: Faker) -> Built:
    """Classic shadow-data: an engineer pastes prod data into a personal note to debug."""
    t = Counter()
    ssn = fk.ssn()
    _, pan = fk.card("plain")
    t.update({"ssn": 1, "credit_card": 1})
    text = (
        "debug notes - DELETE LATER\n\n"
        f"customer record that breaks the import: ssn {ssn}, card {pan}\n"
        f"bad validator input from logs: {fk.decoy_ssn_like()}\n"
    )
    t["decoy_ssn"] += 1
    return text, t


def old_budget(fk: Faker, n: int = 6) -> Built:
    t = Counter()
    rows = [["vendor", "corporate_card", "annual_spend"]]
    for _ in range(n):
        _, pan = fk.card("dashed")
        rows.append([fk.rng.choice(["CloudCo", "PaperCorp", "TravelInc"]), pan, fk.rng.randint(1000, 90000)])
        t["credit_card"] += 1
    return _csv(rows), t


def clean_text(kind: str) -> Built:
    """Non-sensitive files. Most of any real estate is like this - scanners must be cheap on it."""
    texts = {
        "press": "Acme Example Corp announces Q4 product launch.\nRevenue grew 12% year over year.\n",
        "faq": "Open enrollment runs Nov 1-30.\nContact the benefits portal for plan details.\n",
        "q3": "Q3 summary: 4,213 orders shipped, 98.2% on time, 1,024 new customers.\n",
        "design": "# Service design\n\nRetry policy: 3 attempts, backoff 250ms.\nPort 8443, timeout 30000ms.\n",
    }
    return texts[kind], Counter()
