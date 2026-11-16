"""Stage 2 tests: a labeled false-positive gallery.

Each case says what each layer SHOULD report. Read the table top to bottom and you have
the regex vs checksum vs context trade-off in one screen.
(All values are fake: SSN area 9xx, published test card numbers, reserved domains.)
"""

import pytest

from dspm.classifiers import get_classifier
from dspm.compare_levels import score

LAYERS = ["regex-only", "regex-checksum", "regex-context"]

# (snippet, type, expected count per layer [regex-only, checksum, context], lesson)
CASES = [
    ("SSN: 912-34-5678", "ssn", [1, 1, 1], "clean true positive: every layer finds it"),
    ("ssn 912 34 5678", "ssn", [1, 1, 1], "spaced format still matches"),
    ("tin=912345678", "ssn", [1, 1, 1], "bare digits + keyword: context keeps it"),
    ("order 912345678 shipped", "ssn", [1, 1, 0], "FP bait: SSN-shaped order id, only context drops it"),
    ("ssn_field=000-12-3456", "ssn", [1, 0, 0], "FP bait: area 000 is never valid, checksum drops it"),
    ("ref 666-12-3456", "ssn", [1, 0, 0], "FP bait: area 666 is never valid"),
    ("call 912-34 5678", "ssn", [0, 0, 0], "mixed separators: not an SSN shape"),
    ("card 4111 1111 1111 1111", "credit_card", [1, 1, 1], "test Visa, passes Luhn"),
    ("INV 4111111111111112 paid", "credit_card", [1, 0, 0], "FP bait: fails Luhn by one digit"),
    ("serial 9999999999999995", "credit_card", [1, 0, 0], "passes Luhn but no real brand prefix"),
    ("my social is nine one two...", "ssn", [0, 0, 0], "FALSE NEGATIVE for all: spelled out (Stage 6 target)"),
    ("Sozialversicherungsnummer 912345678", "ssn", [1, 1, 0],
     "FALSE NEGATIVE for context: German keyword not in the list"),
]


@pytest.mark.parametrize("snippet,dtype,expected,lesson", CASES, ids=[c[3] for c in CASES])
def test_fp_gallery(snippet, dtype, expected, lesson):
    got = [get_classifier(layer).counts(snippet).get(dtype, 0) for layer in LAYERS]
    assert got == expected, lesson


def test_findings_have_span_confidence_explanation():
    text = "Employee SSN: 912-34-5678"
    [f] = get_classifier("regex").classify(text)
    assert text[f.span[0]:f.span[1]] == "912-34-5678"
    assert 0 < f.confidence <= 1 and "ssn" in f.explanation.lower()


def test_card_digits_not_double_counted_as_ssn():
    found = get_classifier("regex-checksum").counts("pay with 4111111111111111")
    assert found == {"credit_card": 1}


def test_csv_header_counts_as_context():
    csv = "name,tin\nAvery,912345678\n"
    assert get_classifier("regex").counts(csv) == {"ssn": 1}


def test_production_rules_are_blind_to_lab_ssns():
    assert get_classifier("regex-checksum", allow_lab_ssn_area=False).counts("SSN 912-34-5678") == {}


def test_layers_improve_precision_on_lab(lab):
    def precision(name, t):
        c = score(lab, name)[t]
        return c["tp"] / (c["tp"] + c["fp"])
    assert precision("regex-only", "credit_card") < precision("regex-checksum", "credit_card") == 1.0
    assert precision("regex-checksum", "ssn") < precision("regex-context", "ssn") == 1.0


def test_no_deterministic_layer_finds_health_records(lab):
    for layer in LAYERS:
        assert score(lab, layer)["health_record"]["tp"] == 0  # no pattern exists; Stage 6 target
