"""Validators: the "checksum / structure" layer that sits on top of regex.

Regex answers "is this SHAPED like X?". Validators answer "COULD this actually be X?".
They are cheap, deterministic and remove most false positives - but only for data
types that have internal structure. Emails, names and diagnoses have none.
"""

from __future__ import annotations

import re


def digits_only(s: str) -> str:
    return re.sub(r"\D", "", s)


def luhn_ok(number: str) -> bool:
    """Luhn mod-10. Catches every single-digit typo and most transpositions, which is why
    card networks adopted it. For us: a random 16-digit number passes only ~10% of the
    time, so Luhn removes ~90% of card-shaped false positives for free."""
    digits = digits_only(number)
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Issuer prefixes (IIN ranges), simplified. Luhn alone still lets 10% of random numbers
# through; requiring a plausible brand prefix cuts that further.
CARD_PREFIXES = {
    "visa": (r"^4", (13, 16, 19)),
    "mastercard": (r"^(5[1-5]|2[2-7])", (16,)),
    "amex": (r"^3[47]", (15,)),
    "discover": (r"^(6011|65|64[4-9])", (16, 19)),
}


def card_brand(number: str) -> str | None:
    d = digits_only(number)
    for brand, (prefix, lengths) in CARD_PREFIXES.items():
        if re.match(prefix, d) and len(d) in lengths:
            return brand
    return None


def ssn_structure_ok(candidate: str, allow_lab_area: bool = True) -> bool:
    """SSNs have no checksum - only structural rules:
       area != 000, != 666; group != 00; serial != 0000.

    Real validators also reject area 900-999 (never issued). Our lab's fake SSNs live in
    exactly that range so they can never belong to anyone, so lab mode accepts 9xx.
    Set allow_lab_area=False to see production behaviour: recall on lab data drops to 0.
    That's a real lesson: a validator tuned to reality can be blind to test data, and
    vice-versa.
    """
    d = digits_only(candidate)
    if len(d) != 9:
        return False
    area, group, serial = int(d[:3]), int(d[3:5]), int(d[5:])
    if area in (0, 666) or group == 0 or serial == 0:
        return False
    if area >= 900 and not allow_lab_area:
        return False
    return True
