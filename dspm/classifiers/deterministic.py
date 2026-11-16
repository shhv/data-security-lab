"""Deterministic classifiers: three layers, each = previous layer + one idea.

    regex-only      shape matching.          Cheap, high recall, noisy.
    regex-checksum  + Luhn / SSN structure.  Kills most card FPs; SSNs have no checksum,
                                             so 9-digit order IDs still get through.
    regex-context   + keyword proximity.     "Corroborative evidence" (Purview's term).
                                             Bare 9 digits count only near ssn/tin/social.

Trade-off summary (you'll measure these in `python -m dspm.compare_levels`):
- Regex knows FORMAT, not MEANING. "123-45-6789" in an SSN column and in a part catalog
  look identical to it.
- Checksums add MEANING only where the data type has math built in (cards: yes, SSNs:
  weak structure only, emails/health: none).
- Context adds MEANING from surrounding words. It's still deterministic and explainable,
  but brittle: a German "Sozialversicherungsnummer" or "my social is..." in words slips
  past unless someone adds the keyword. Stage 6 measures whether an LLM does better.
"""

from __future__ import annotations

import re

from .base import Classifier, Finding
from .validators import card_brand, digits_only, luhn_ok, ssn_structure_ok

# Separator captured and back-referenced (\2) so "123-45 6789" doesn't match.
SSN_RE = re.compile(r"(?<![\d-])(\d{3})([-\s.]?)(\d{2})\2(\d{4})(?![\d-])")
CARD_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _kw(words: list[str]) -> re.Pattern:
    # Letter boundaries, not \b: "ssn_field" and "card_number" should count,
    # but "tin" inside "settings" should not.
    return re.compile(r"(?<![a-z])(" + "|".join(words) + r")(?![a-z])", re.I)


SSN_KEYWORDS = _kw(["ssn", "social security", "social", "tin", "taxpayer", "tax id"])
CARD_KEYWORDS = _kw(["card", "credit", "debit", "visa", "mastercard", "amex", "pan", "payment"])

CONTEXT_WINDOW = 50  # chars before the match on the same line


def context_for(text: str, start: int) -> str:
    """Text a human would use to judge the match: preceding words on the line, plus the
    CSV column header if the file looks like a CSV. (Naive: ignores quoted commas.)"""
    line_start = text.rfind("\n", 0, start) + 1
    before = text[max(line_start, start - CONTEXT_WINDOW):start]
    header = text[: text.find("\n")] if "\n" in text else ""
    if "," in header and line_start > 0:
        col = text[line_start:start].count(",")
        cols = header.split(",")
        if col < len(cols):
            before = f"[column: {cols[col]}] {before}"
    return before


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


class RegexOnlyClassifier(Classifier):
    name = "regex-only"

    def classify(self, text: str) -> list[Finding]:
        out = [Finding("email", m.span(), 0.9, "email pattern (no checksum exists for emails)", m.group())
               for m in EMAIL_RE.finditer(text)]
        out += [Finding("credit_card", m.span(), 0.4, "13-19 digit card shape", m.group())
                for m in CARD_RE.finditer(text)]
        out += [Finding("ssn", m.span(), 0.4, "NNN-NN-NNNN shape (or 9 bare digits)", m.group())
                for m in SSN_RE.finditer(text)]
        return out


class ChecksumClassifier(Classifier):
    name = "regex-checksum"

    def __init__(self, allow_lab_ssn_area: bool = True):
        self.allow_lab_ssn_area = allow_lab_ssn_area

    def _cards(self, text: str) -> list[Finding]:
        out = []
        for m in CARD_RE.finditer(text):
            brand = card_brand(m.group())
            if luhn_ok(m.group()) and brand:
                out.append(Finding("credit_card", m.span(), 0.85, f"passes Luhn, {brand} prefix/length", m.group()))
        return out

    def _ssns(self, text: str, cards: list[Finding]) -> list[Finding]:
        out = []
        for m in SSN_RE.finditer(text):
            if any(_overlaps(m.span(), c.span) for c in cards):
                continue  # digits belong to a card, don't double count
            if ssn_structure_ok(m.group(), self.allow_lab_ssn_area):
                out.append(Finding("ssn", m.span(), 0.6, "SSN shape + valid area/group/serial", m.group()))
        return out

    def classify(self, text: str) -> list[Finding]:
        emails = RegexOnlyClassifier().classify(text)
        emails = [f for f in emails if f.type == "email"]
        cards = self._cards(text)
        return emails + cards + self._ssns(text, cards)


class ContextClassifier(ChecksumClassifier):
    """The full deterministic pipeline. This is what `--classifier regex` means."""
    name = "regex-context"

    def classify(self, text: str) -> list[Finding]:
        out = []
        for f in super().classify(text):
            if f.type == "email":
                out.append(f)
                continue
            kw_re = SSN_KEYWORDS if f.type == "ssn" else CARD_KEYWORDS
            ctx = context_for(text, f.span[0])
            kw = kw_re.search(ctx)
            formatted = digits_only(f.value) != f.value  # has separators
            if kw:
                out.append(Finding(f.type, f.span, 0.95, f"{f.explanation}; keyword '{kw.group()}' nearby", f.value))
            elif f.type == "credit_card":
                out.append(Finding(f.type, f.span, 0.75, f"{f.explanation}; no keyword", f.value))
            elif formatted:
                out.append(Finding(f.type, f.span, 0.6, f"{f.explanation}; formatted, no keyword", f.value))
            # bare 9 digits with no keyword: dropped - too likely an order/employee/part ID
        return out
