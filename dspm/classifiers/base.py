"""The common Classifier interface.

Why an interface first? The DSPM scanner and DLP engine should not care HOW data was
classified - regex, checksum, LLM, or a cascade. They only consume Findings. This is the
same separation identity systems use: an app consumes a token's claims and doesn't care
which IdP (Entra, Okta, Google) or which auth method (password, FIDO2) produced them.

A Finding carries:
- type        what kind of data ("ssn", "credit_card", "email", ...)
- span        (start, end) character offsets into the text, or None when the classifier
              can't point at exact characters (common for LLMs and for "no-pattern" data
              like a sentence describing a diagnosis)
- confidence  0.0-1.0. Policies use thresholds on this (e.g. block only if >= 0.85)
- explanation why it fired. Auditors and users who get blocked will ask exactly this.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    type: str
    span: tuple[int, int] | None
    confidence: float
    explanation: str
    value: str | None = None  # matched text; never log this outside the lab

    def to_dict(self) -> dict:
        return asdict(self)


class Classifier(ABC):
    name: str = "base"

    @abstractmethod
    def classify(self, text: str) -> list[Finding]:
        """Return all sensitive-data findings in `text`. Must never raise on odd input."""

    def counts(self, text: str, min_confidence: float = 0.0) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.classify(text):
            if f.confidence >= min_confidence:
                out[f.type] = out.get(f.type, 0) + 1
        return out
