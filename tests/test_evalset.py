"""Stage 6 step 2: the labeled eval set is well-formed, hard, and fake."""

import json
import re
from collections import Counter

from datagen.evalset import build, load
from datagen.fakes import TEST_CARDS
from dspm.classifiers import get_classifier
from eval.scoring import counts, evaluate, prf

CATEGORIES = {"clean", "formatted", "fp_bait", "context", "no_pattern", "obfuscated", "non_english"}


def test_size_and_categories():
    rows = build()
    assert 190 <= len(rows) <= 210
    assert {r["category"] for r in rows} == CATEGORIES
    assert len({r["id"] for r in rows}) == len(rows)


def test_spans_point_at_the_labeled_text():
    for r in build():
        for lab in r["labels"]:
            assert r["text"][lab["start"]:lab["end"]] == lab["value"], r["id"]


def test_fp_bait_has_no_labels_and_context_is_paired():
    rows = build()
    assert all(not r["labels"] for r in rows if r["category"] == "fp_bait")
    ctx = [r for r in rows if r["category"] == "context"]
    assert Counter(bool(r["labels"]) for r in ctx) == {True: 15, False: 15}


def test_snippets_file_contains_no_labels(lab):
    for line in (lab / "eval" / "snippets.jsonl").open():
        assert "labels" not in json.loads(line)  # a classifier must never see answers


def test_load_roundtrip(lab):
    assert [(r["id"], r["labels"]) for r in load(lab)] == [(r["id"], r["labels"]) for r in build()]


def test_only_fake_values():
    test_pans = {p for v in TEST_CARDS.values() for p in v}
    for r in build():
        for lab in r["labels"]:
            if lab["type"] == "credit_card" and re.fullmatch(r"[\d .-]+", lab["value"]):
                assert re.sub(r"\D", "", lab["value"]) in test_pans
            if lab["type"] == "ssn" and re.fullmatch(r"[\d .-]+", lab["value"]):
                assert re.sub(r"\D", "", lab["value"])[0] == "9"
        for domain in re.findall(r"@([\w.-]+)", r["text"]):
            assert domain.lower().endswith(".example") or domain in {"example.com"}


def test_regex_baseline_shows_the_gaps(lab):
    """Document the deterministic baseline so Stage 6 has something to beat."""
    by_cat = counts(evaluate(get_classifier("regex"), load(lab)), lambda s, t: s["category"])
    assert prf(by_cat["clean"])[1] == 1.0          # easy cases: perfect recall
    assert by_cat["no_pattern"]["tp"] == 0         # no pattern -> nothing found
    assert prf(by_cat["obfuscated"])[1] < 0.2      # evasion beats regex
    assert by_cat["context"]["fp"] > 0             # dashed "part numbers" still flagged
