"""Classifier registry. Everything downstream asks for a classifier BY NAME, so adding the
LLM and hybrid classifiers in Stage 6 is a one-line change here, not a refactor."""

from .base import Classifier, Finding
from .deterministic import ChecksumClassifier, ContextClassifier, RegexOnlyClassifier

REGISTRY: dict[str, type[Classifier]] = {
    "regex-only": RegexOnlyClassifier,
    "regex-checksum": ChecksumClassifier,
    "regex-context": ContextClassifier,
}
ALIASES = {"regex": "regex-context"}  # the deterministic default
DEFAULT = "regex"


def get_classifier(name: str = DEFAULT, **kwargs) -> Classifier:
    key = ALIASES.get(name, name)
    if key not in REGISTRY:
        raise ValueError(f"unknown classifier {name!r}; choose from {sorted(REGISTRY) + sorted(ALIASES)}")
    return REGISTRY[key](**kwargs)


__all__ = ["Classifier", "Finding", "get_classifier", "REGISTRY", "DEFAULT"]
