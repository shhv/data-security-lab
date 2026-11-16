"""Stage 1 tests: the lab is reproducible, consistent, and provably fake."""

import json
import re

from datagen.fakes import TEST_CARDS, Faker, luhn_checksum_ok
from datagen.generate import ACCOUNT, generate


def load(lab, name):
    return json.loads((lab / name).read_text())


def test_same_seed_same_lab(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate(a, seed=7)
    generate(b, seed=7)
    for f in (a / "storage").rglob("*"):
        if f.is_file():
            assert f.read_bytes() == (b / f.relative_to(a)).read_bytes()


def test_manifest_matches_files_on_disk(lab):
    manifest = load(lab, "manifest.json")
    on_disk = {p.relative_to(lab / "storage" / ACCOUNT).as_posix()
               for p in (lab / "storage").rglob("*") if p.is_file()}
    assert on_disk == set(manifest["files"])


def test_mix_of_sensitive_and_clean_files(lab):
    files = load(lab, "manifest.json")["files"].values()
    assert any(f["sensitive"] for f in files)
    assert any(not f["sensitive"] for f in files)


def test_ssns_are_never_issuable():
    fk = Faker(1)
    for _ in range(500):
        area, group, _ = fk.ssn().split("-")
        assert 900 <= int(area) <= 999          # never issued as SSN
        assert 1 <= int(group) <= 49            # outside ITIN group ranges


def test_cards_are_test_pans_and_pass_luhn():
    fk = Faker(1)
    all_test = {p for pans in TEST_CARDS.values() for p in pans}
    for _ in range(100):
        _, pan = fk.card(fk.rng.choice(["plain", "spaced", "dashed"]))
        digits = re.sub(r"\D", "", pan)
        assert digits in all_test and luhn_checksum_ok(digits)


def test_card_decoys_fail_luhn():
    fk = Faker(1)
    assert not any(luhn_checksum_ok(fk.decoy_card_like()) for _ in range(100))


def test_only_reserved_email_domains(lab):
    pattern = re.compile(r"[\w.+-]+@([\w.-]+)")
    for f in (lab / "storage").rglob("*"):
        if f.is_file():
            for domain in pattern.findall(f.read_text()):
                assert domain.endswith(".example") or domain in {"example.com", "example.org"}, domain


def test_every_acl_principal_exists(lab):
    perms = load(lab, "permissions.json")
    ids = {u["id"] for u in perms["users"]} | {g["id"] for g in perms["groups"]}
    for g in perms["groups"]:
        assert set(g["members"]) <= ids, g["id"]
    for path, acl in perms["acls"].items():
        assert acl["owner"] in ids
        for gr in acl["grants"]:
            kind, _, ref = gr["principal"].partition(":")
            if kind in ("user", "group"):
                assert ref in ids, (path, gr)
            else:
                assert kind in ("anyone_with_link", "domain"), (path, gr)
