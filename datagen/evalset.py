"""Labeled evaluation set (~200 short snippets) for comparing classifiers.

Two files, kept apart on purpose:
    eval/snippets.jsonl   {id, category, lang, text, note}   <- what a classifier sees
    eval/labels.jsonl     {id, type, start, end, value}      <- the answer key

Separating them is the same idea as never shipping the test answers with the exam:
the LLM classifier only ever receives `text`, so it can't "cheat" by reading labels.

Labels are SPAN-level (character offsets), not counts. That closes the Stage 2 gap where
"missed one SSN + flagged one decoy" in the same file scored as perfect.

Types:
    ssn, credit_card, email          have patterns - regex can find them
    health, salary, address          no fixed pattern - regex can't, by design

Categories (the hard cases Stage 6 asked for):
    clean, formatted, fp_bait, context, no_pattern, obfuscated, non_english
"""

from __future__ import annotations

import json
from pathlib import Path

from .fakes import TEST_CARDS, Faker

Snippet = tuple[str, list[tuple[str, str]], str]  # (text, [(type, value-substring)], note)

DIGIT_WORDS = "zero one two three four five six seven eight nine".split()


def _say(digits: str) -> str:
    return " ".join(DIGIT_WORDS[int(d)] for d in digits if d.isdigit())


def _card(fk: Faker, sep: str = "") -> str:
    pan = fk.rng.choice([p for pans in TEST_CARDS.values() for p in pans])
    if sep:
        pan = sep.join(pan[i:i + 4] for i in range(0, len(pan), 4))
    return pan


def _person_email(fk: Faker, domain: str = "acme.example") -> str:
    return fk.email(*fk.name(), domain)


# --- builders: each returns a list of Snippets for one category -----------------------
def clean(fk: Faker) -> list[Snippet]:
    """Easy true positives in canonical formats. Every classifier should ace these."""
    out = []
    for _ in range(10):
        s = fk.ssn()
        out.append((f"Employee SSN: {s}", [("ssn", s)], "canonical dashed SSN"))
    for _ in range(10):
        c = _card(fk)
        out.append((f"Card number: {c}", [("credit_card", c)], "plain test PAN"))
    for _ in range(10):
        e = _person_email(fk)
        out.append((f"Contact: {e}", [("email", e)], "plain email"))
    return out


def formatted(fk: Faker) -> list[Snippet]:
    """Same data, different punctuation. Tests how forgiving each pattern is."""
    out = []
    for fmt, tmpl in [("spaced", "SSN {}"), ("dotted", "social security no. {}"),
                      ("bare", "tin={}")] * 3 + [("spaced", "ssn: {}")]:
        s = fk.ssn(fmt)
        out.append((tmpl.format(s), [("ssn", s)], f"{fmt} SSN"))
    for sep, note in [(" ", "spaced card"), ("-", "dashed card"), (".", "dotted card (regex allows only space/dash)")] * 3:
        c = _card(fk, sep)
        out.append((f"Payment card {c} exp 12/29", [("credit_card", c)], note))
    amex = "3782 822463 10005"
    out.append((f"Amex on file: {amex}", [("credit_card", amex)], "Amex 4-6-5 grouping"))
    first, last = fk.name()
    for e, note in [
        (f"{first}.{last}+payroll@acme.example", "plus-addressing"),
        (f"{first.upper()}.{last.upper()}@ACME.EXAMPLE", "uppercase"),
        (f"{first.lower()}@mail.eu.partner.example", "multi-level subdomain"),
        (f"{first.lower()}_{last.lower()}@personalmail.example", "underscore"),
        (f"<{first.lower()}@example.com>", "angle brackets"),
    ] * 2:
        value = e.strip("<>")
        out.append((f"Reply-To: {e}", [("email", value)], note))
    return out


def fp_bait(fk: Faker) -> list[Snippet]:
    """Look sensitive, aren't. Every label list is EMPTY - any finding is a false positive."""
    out = []
    for _ in range(8):
        out.append((f"Order {fk.order_id()} shipped via ground", [], "9-digit order id"))
    for _ in range(6):
        out.append((f"Invoice {fk.decoy_card_like()} paid", [], "16 digits, fails Luhn"))
    for _ in range(2):
        out.append((f"Card number on file: {fk.decoy_card_like()} (rejected by processor)", [],
                    "card keyword but fails Luhn - a typo, not a real PAN"))
    for _ in range(4):
        v = f"{fk.rng.randint(900, 999)}.{fk.rng.randint(10, 49)}.{fk.rng.randint(1000, 9999)}"
        out.append((f"Deployed build {v} to staging", [], "version string shaped like a dotted SSN"))
    for _ in range(4):
        out.append((f"ssn_field rejected: {fk.decoy_ssn_like()}", [], "structurally invalid SSN (000/666/00)"))
    for _ in range(4):
        out.append((f"Call support at {fk.phone()}", [], "phone number (555-01xx fiction range)"))
    out += [
        ("Backup finished 2026-11-14 10:22:33 UTC", [], "timestamp"),
        ("Batch 20261114 processed 912 records in 34.5678s", [], "digits near each other"),
        ("Join the diabetes awareness walk this Saturday!", [], "health TOPIC, no patient"),
        ("Our plan covers asthma inhalers and allergy tests.", [], "health TOPIC, no patient"),
        ("Flu shots available in the lobby on Tuesday.", [], "health TOPIC, no patient"),
        ("Q3 report: hypertension is the most common claim category.", [], "aggregate, not personal"),
        ("Industry survey: average analyst salary is $95,000.", [], "aggregate salary, not personal"),
        ("Salary bands are published on the intranet.", [], "salary TOPIC"),
        ("Posted range for this role: $120k-$150k.", [], "job posting, not a person's pay"),
        ("Acme HQ: 1 Example Plaza, Testville, ZZ 00000", [], "company address, not a home"),
        ("Visitors park at 200 Sample Rd, Testville.", [], "business address"),
        ("Mail checks to PO Box 100, Testville, ZZ 00000", [], "business PO box"),
    ]
    return out


def context(fk: Faker) -> list[Snippet]:
    """Pairs: IDENTICAL digits, different meaning. Only the sentence tells them apart.
    IAM analogy: the same GUID can be an objectId, an appId or a tenantId - you need the
    claim name, not just the value."""
    pairs = [
        ("Employee ID {} assigned to badge reader 4", "Employee SSN {} for the W-2"),
        ("Part number {} back in stock", "Social: {}"),
        ("Ticket {} closed by helpdesk", "her social security number is {}"),
        ("Account no. {} (loyalty program)", "Taxpayer ID {} on the 1099"),
        ("Room booking ref {}", "SSN on the background check: {}"),
    ]
    out = []
    for i in range(15):
        neg, pos = pairs[i % len(pairs)]
        s = fk.ssn(["bare", "dashed", "spaced"][i % 3])  # SAME value in both halves
        out.append((neg.format(s), [], "same digits used as a non-SSN identifier"))
        out.append((pos.format(s), [("ssn", s)], "same digits explicitly called an SSN"))
    return out


def no_pattern(fk: Faker) -> list[Snippet]:
    """Sensitive meaning, no fixed shape. The whole sentence (or phrase) is the label."""
    out = []
    health = [
        "{n} was diagnosed with type 2 diabetes last March.",
        "Patient {n} is being treated for generalized anxiety disorder.",
        "{n}'s chart notes stage 1 hypertension; follow up in 6 weeks.",
        "{n} disclosed an HIV-positive status during intake.",
        "Per the clinic, {n} is undergoing chemotherapy for breast cancer.",
        "{n} has a documented penicillin allergy and asthma.",
        "Medical leave approved: {n} is recovering from knee surgery.",
        "{n} tested positive for COVID-19 on Monday and is isolating.",
        "Therapist note: {n} reports depressive episodes since spring.",
        "{n} is pregnant and due in April; adjust duties accordingly.",
    ]
    for t in health:
        n = " ".join(fk.name())
        s = t.format(n=n)
        out.append((s, [("health", s)], "individual + medical condition"))
    for _ in range(10):
        n = " ".join(fk.name())
        amt = f"${fk.rng.randint(55, 240)},{fk.rng.randint(0, 9)}00"
        t = fk.rng.choice(["{n}'s base salary is {a} per year.",
                           "Offer letter: {n}, annual compensation {a}.",
                           "Raise approved - {n} moves to {a}."])
        s = t.format(n=n, a=amt)
        out.append((s, [("salary", amt)], "named individual + pay amount"))
    streets = ["Placeholder Lane", "Fixture Court", "Sample Street", "Mockingbird Way", "Stub Avenue"]
    for _ in range(10):
        n = " ".join(fk.name())
        addr = (f"{fk.rng.randint(10, 9999)} {fk.rng.choice(streets)}, Testville, "
                f"ZZ {fk.rng.randint(0, 99):05d}")
        t = fk.rng.choice(["{n} lives at {a}.", "Home address for {n}: {a}",
                           "Ship {n}'s laptop to their home: {a}"])
        out.append((t.format(n=n, a=addr), [("address", addr)], "home address of a person"))
    return out


def obfuscated(fk: Faker) -> list[Snippet]:
    """Deliberate or accidental evasion. Regex has no chance; does an LLM?"""
    out = []
    for _ in range(5):
        words = _say(fk.ssn("bare"))
        out.append((f"my social is {words}", [("ssn", words)], "SSN spelled out in words"))
    leet = str.maketrans({"1": "l", "5": "S", "0": "O"})
    for _ in range(4):
        s = fk.ssn()
        while not any(ch in s for ch in "150"):
            s = fk.ssn()
        v = s.translate(leet)
        out.append((f"ssn: {v}", [("ssn", v)], "look-alike letters (l for 1, S for 5, O for 0)"))
    for _ in range(3):
        a, b, c = fk.ssn("spaced").split()
        v = f"{a} / {b} / {c}"
        out.append((f"SSN goes {v} - don't tell anyone", [("ssn", v)], "slashes break the regex"))
    for _ in range(4):
        words = _say(_card(fk))
        out.append((f"card is {words}", [("credit_card", words)], "card spelled out in words"))
    for _ in range(4):
        first, last = (x.lower() for x in fk.name())
        v = f"{first} dot {last} at acme dot example"
        out.append((f"email me: {v}", [("email", v)], "email written as words to dodge filters"))
    return out


def non_english(fk: Faker) -> list[Snippet]:
    """Same data types, other languages. Keyword lists are usually English-only."""
    out = []

    def ssn(t, lang, fmt="bare"):
        s = fk.ssn(fmt)
        out.append((t.format(s), [("ssn", s)], "US SSN in non-English text", lang))

    def card(t, lang):
        c = _card(fk, " ")
        out.append((t.format(c), [("credit_card", c)], "card in non-English text", lang))

    ssn("Die US-Sozialversicherungsnummer des Mitarbeiters lautet {}.", "de")
    ssn("Sozialversicherungsnummer: {}", "de")
    ssn("Mi número de seguro social es {}.", "es")
    ssn("Número de Seguro Social del empleado: {}", "es")
    ssn("Numéro de sécurité sociale américain : {}", "fr")
    ssn("社会保障番号は {} です。", "ja")
    card("Numéro de carte bancaire : {}", "fr")
    card("Número de tarjeta: {}, vence 12/29", "es")
    card("Kreditkartennummer {} bitte belasten", "de")
    card("Número do cartão de crédito: {}", "pt")
    e = _person_email(fk)
    out.append((f"Correo electrónico del cliente: {e}", [("email", e)], "email, Spanish", "es"))
    e = _person_email(fk, "partner.example")
    out.append((f"E-Mail-Adresse: {e}", [("email", e)], "email, German", "de"))
    for t, lang in [("{n} wurde mit Asthma diagnostiziert.", "de"),
                    ("{n} padece de diabetes tipo 2 y toma insulina.", "es"),
                    ("Le patient {n} souffre d'hypertension sévère.", "fr")]:
        s = t.format(n=" ".join(fk.name()))
        out.append((s, [("health", s)], "medical condition, non-English", lang))
    for t, lang in [("O salário anual de {n} é {a}.", "pt"), ("Das Jahresgehalt von {n} beträgt {a}.", "de")]:
        a = f"${fk.rng.randint(60, 200)},000"
        out.append((t.format(n=" ".join(fk.name()), a=a), [("salary", a)], "salary, non-English", lang))
    for t, lang in [("{n} vive en {a}.", "es"), ("{n} habite au {a}.", "fr"), ("{n} wohnt in {a}.", "de")]:
        a = f"{fk.rng.randint(10, 999)} Sample Street, Testville, ZZ 00000"
        out.append((t.format(n=" ".join(fk.name()), a=a), [("address", a)], "home address, non-English", lang))
    return out


def build(seed: int = 1337) -> list[dict]:
    fk = Faker(seed)
    categories = {
        "clean": clean, "formatted": formatted, "fp_bait": fp_bait, "context": context,
        "no_pattern": no_pattern, "obfuscated": obfuscated, "non_english": non_english,
    }
    rows = []
    for cat, fn in categories.items():
        for text, labels, note, *lang in fn(fk):
            sid = f"{cat}-{sum(r['category'] == cat for r in rows) + 1:03d}"
            spans = []
            for typ, value in labels:
                start = text.index(value)  # raises if a builder mislabels: fail loudly
                spans.append({"type": typ, "start": start, "end": start + len(value), "value": value})
            rows.append({"id": sid, "category": cat, "lang": lang[0] if lang else "en",
                         "text": text, "note": note, "labels": spans})
    return rows


def write(out: Path, seed: int = 1337) -> dict:
    out = Path(out) / "eval"
    out.mkdir(parents=True, exist_ok=True)
    rows = build(seed)
    with (out / "snippets.jsonl").open("w", encoding="utf-8") as s, \
         (out / "labels.jsonl").open("w", encoding="utf-8") as lab:
        for r in rows:
            s.write(json.dumps({k: r[k] for k in ("id", "category", "lang", "text", "note")},
                               ensure_ascii=False) + "\n")
            for span in r["labels"]:
                lab.write(json.dumps({"id": r["id"], **span}, ensure_ascii=False) + "\n")
    return {"snippets": len(rows), "labels": sum(len(r["labels"]) for r in rows)}


def load(lab_dir: Path) -> list[dict]:
    """Join snippets with their labels (for scoring code - never pass labels to a classifier)."""
    d = Path(lab_dir) / "eval"
    rows = [json.loads(line) for line in (d / "snippets.jsonl").open(encoding="utf-8")]
    by_id = {r["id"]: r | {"labels": []} for r in rows}
    for line in (d / "labels.jsonl").open(encoding="utf-8"):
        lab = json.loads(line)
        by_id[lab.pop("id")]["labels"].append(lab)
    return list(by_id.values())
