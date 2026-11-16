"""Fake value generators.

Every generator here is designed so its output CANNOT be real:

- SSNs use area 900-999. The SSA never issues SSNs in that range, and we keep the
  group number at 01-49, which is also outside the ITIN ranges (9XX-50..99-XXXX).
  Trade-off: a real-world validator rejects 9XX areas. In Stage 2 you'll see why
  that matters and how the lab handles it.
- Credit cards are drawn from publicly documented processor TEST numbers. They pass
  the Luhn checksum (so they look real to a detector) but are not tied to any account.
- Email domains use RFC 2606 / RFC 6761 reserved names (*.example), which can never
  be registered by anyone.

Decoys are just as important as true positives: a detector is only as good as its
false-positive rate, so we deliberately generate numbers that LOOK sensitive but aren't.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

TENANT_DOMAIN = "acme.example"            # our "company" (think: Entra tenant / Workspace primary domain)
PARTNER_DOMAIN = "partner.example"        # B2B partner org (guest accounts come from here)
PERSONAL_DOMAIN = "personalmail.example"  # stand-in for gmail/outlook.com personal accounts

FIRST_NAMES = [
    "Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sasha",
    "Emerson", "Harper", "Kai", "Logan", "Parker", "Reese", "Skyler", "Tatum",
]
LAST_NAMES = [
    "Testwell", "Sampleton", "Mockford", "Fakesley", "Dummond", "Placeholt",
    "Synthia", "Labrador", "Fixture", "Stubbs", "Nullman", "Datawright",
]

# Publicly documented test PANs (Stripe / Braintree / network sandbox docs).
TEST_CARDS = {
    "visa": ["4111111111111111", "4012888888881881", "4242424242424242"],
    "mastercard": ["5555555555554444", "5105105105105100"],
    "amex": ["378282246310005", "371449635398431"],
    "discover": ["6011111111111117", "6011000990139424"],
}

# Real ICD-10 codes are public reference data (not PII); the pairing with fake people is what's sensitive.
DIAGNOSES = [
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("I10", "Essential (primary) hypertension"),
    ("J45.909", "Unspecified asthma, uncomplicated"),
    ("F41.1", "Generalized anxiety disorder"),
    ("M54.5", "Low back pain"),
]


def luhn_checksum_ok(number: str) -> bool:
    """Luhn mod-10 check. Duplicated (intentionally) from what you'll build in Stage 2,
    because the generator needs it to make *failing* decoys."""
    digits = [int(d) for d in number if d.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class Faker:
    """Tiny seeded faker. Same seed => same lab every time (reproducible experiments)."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    # --- identity-ish -------------------------------------------------------
    def name(self) -> tuple[str, str]:
        return self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)

    def email(self, first: str, last: str, domain: str = TENANT_DOMAIN) -> str:
        return f"{first.lower()}.{last.lower()}{self.rng.randint(1, 99)}@{domain}"

    def dob(self) -> str:
        start = date(1950, 1, 1)
        return (start + timedelta(days=self.rng.randint(0, 365 * 50))).isoformat()

    # --- sensitive values ---------------------------------------------------
    def ssn(self, fmt: str = "dashed") -> str:
        area = self.rng.randint(900, 999)    # never issued as SSN
        group = self.rng.randint(1, 49)      # outside ITIN group ranges
        serial = self.rng.randint(1, 9999)
        if fmt == "dashed":
            return f"{area:03d}-{group:02d}-{serial:04d}"
        if fmt == "spaced":
            return f"{area:03d} {group:02d} {serial:04d}"
        if fmt == "dotted":
            return f"{area:03d}.{group:02d}.{serial:04d}"
        return f"{area:03d}{group:02d}{serial:04d}"  # bare 9 digits: hardest to detect

    def card(self, fmt: str = "plain") -> tuple[str, str]:
        brand = self.rng.choice(list(TEST_CARDS))
        pan = self.rng.choice(TEST_CARDS[brand])
        if fmt == "spaced":
            pan = " ".join(pan[i:i + 4] for i in range(0, len(pan), 4))
        elif fmt == "dashed":
            pan = "-".join(pan[i:i + 4] for i in range(0, len(pan), 4))
        return brand, pan

    def mrn(self) -> str:
        """Medical record number. No standard format exists, which is exactly why
        health data is hard to detect with patterns alone."""
        return f"MRN-{self.rng.randint(1000000, 9999999)}"

    def diagnosis(self) -> tuple[str, str]:
        return self.rng.choice(DIAGNOSES)

    # --- decoys (look sensitive, aren't) ---------------------------------------
    def decoy_ssn_like(self) -> str:
        """9 digits in SSN shape but structurally invalid (area 000 or 666, or group 00)."""
        kind = self.rng.choice(["area000", "area666", "group00"])
        serial = self.rng.randint(1, 9999)
        if kind == "area000":
            return f"000-{self.rng.randint(1, 99):02d}-{serial:04d}"
        if kind == "area666":
            return f"666-{self.rng.randint(1, 99):02d}-{serial:04d}"
        return f"{self.rng.randint(900, 999)}-00-{serial:04d}"

    def decoy_card_like(self) -> str:
        """16 digits starting with 4 (looks like Visa) that FAIL Luhn - e.g. an order number."""
        while True:
            num = "4" + "".join(str(self.rng.randint(0, 9)) for _ in range(15))
            if not luhn_checksum_ok(num):
                return num

    def phone(self) -> str:
        """555-01xx is reserved for fiction in the NANP."""
        return f"(202) 555-01{self.rng.randint(0, 99):02d}"

    def order_id(self) -> str:
        return str(self.rng.randint(100_000_000, 999_999_999))  # 9 digits, SSN-shaped!

    def date_between(self, start: date, end: date) -> date:
        return start + timedelta(days=self.rng.randint(0, (end - start).days))
