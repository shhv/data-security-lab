# Data Security Lab: DSPM + DLP

A local, synthetic-data lab for learning **Data Security Posture Management** and
**Data Loss Prevention**. It doesn't use any cloud accounts or real data.

## Two questions, two disciplines

| | DSPM | DLP |
|---|---|---|
| Question | *Where is sensitive data, and who **could** reach it?* | *Should **this** movement of data happen right now?* |
| When | Continuously, at rest | Inline, at the moment of an action (upload, share, email) |
| IAM analogy | An **access review / entitlement report**: effective permissions over resources | A **conditional access policy**: evaluate a live request, then allow/block/step-up |
| Lab module | `dspm/` (Stages 2–3) | `dlp/` + `policies/` (Stage 4) |

Both depend on **classification**, so you can't protect data until you know what it is.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m datagen --out lab_data --seed 42
.venv/bin/pytest -q
```

## Stage 1: the synthetic estate (`datagen/`)

```
lab_data/
  storage/acmeprodstorage/        one "storage account" (≈ SharePoint tenant / GCS project / Azure Storage)
    hr-share/  finance/  clinical/  engineering/  marketing/  support/  shared-drive/
  permissions.json                directory (users, guests, nested groups) + ACLs
  manifest.json                   ground truth: what was planted in each file (the answer key)
```

**Why the data can't be real**
- SSNs use area `900–999` with group `01–49`. The SSA never issues SSNs with those area numbers, and those group numbers fall outside ITIN ranges.
- Card numbers come only from published processor **test** numbers. They pass Luhn but don't belong to any account.
- Every email domain is RFC 2606 reserved (`*.example`, `example.com/org`), and phone numbers use `555-01xx`.

**Why there are decoys**
- About as many fake-looking values are planted as real ones: 9-digit order IDs, SSN-shaped strings with invalid areas (`000`, `666`), and 16-digit invoice IDs that fail Luhn.
- A classifier with great recall and terrible precision buries analysts in alerts. Stage 2 measures both against `manifest.json`.

**Permissions model (`permissions.json`)**
- `users[]`: members, a **disabled leaver** still in groups, and two **B2B guests** with `#EXT#` UPNs.
- `groups[]`: these are **nested**. For example, `grp-eng-extended` contains `grp-contractors`, which contains guest `g01`. Working out who has access requires transitive expansion, the same as resolving group claims.
- `acls{path}`: container grants are **inherited** unless a child sets `inherit: false`. Principals are `user:`, `group:`, `domain:` (org-wide link), and `anyone_with_link` (unauthenticated).

**Planted findings.** Each one has a `note` in `manifest.json`:

| File | Problem |
|---|---|
| `support/tickets/ticket_1042.txt` | Card number in a ticket, shared by public link |
| `shared-drive/u08/debug_notes.txt` | Prod SSN and card copied into a personal note (shadow data), public link |
| `hr-share/payroll/...` | Shared to "Everyone", which includes guests |
| `engineering/logs/...` | Guest reaches it only through two levels of group nesting |
| `clinical/exports/...` | Shared to an external guest through an expired grant |
| `shared-drive/u04/budget_2022.csv` | Stale, org-wide link, card numbers |
| `hr-share/terminations/...` | Stale, owned by a disabled account (orphaned) |
| `marketing/public/press_release.txt` | Public **and fine**: exposure alone isn't a finding |

## Stage 2: classification (`dspm/classifiers/`)

Every classifier implements one interface: `classify(text) -> list[Finding]`, where a
`Finding` has type, span, confidence and explanation. The scanner and DLP engine
ask for a classifier by name (`get_classifier("regex")`), like an app consuming token
claims without caring which IdP issued them.

```bash
.venv/bin/python -m dspm.compare_levels lab_data
.venv/bin/python -m dspm.compare_levels lab_data --production-ssn-rules
```

| Layer | Adds | SSN precision | Card precision | Health recall |
|---|---|---|---|---|
| `regex-only` | shape matching | 0.50 | 0.73 | 0 |
| `regex-checksum` | Luhn + brand prefix, SSN structure rules | 0.53 | **1.00** | 0 |
| `regex-context` (`regex`) | keyword near match or in the CSV column header | **1.00** | 1.00 | 0 |

**What the table teaches**
- **Checksums work only where the data has math built in.** Luhn removed every fake card number, but SSNs have only weak structural rules, so 9-digit order IDs got through.
- **Context fixes meaning but is brittle.** It scores perfectly here because the keywords were chosen with this data in view, which is overfitting. `tests/test_classifiers.py` shows it missing a German keyword and a spelled-out SSN.
- **No pattern exists for health data.** All three layers get 0 recall on it. That gap is what Stage 6 (the LLM classifier) targets.
- **Validators tuned to reality are blind to test data.** With `--production-ssn-rules`, recall on the lab's fake 9xx SSNs drops to 0. The only remaining "SSNs" are order IDs that happen to have valid real-world structure: 34 false positives with zero true positives.

## Mapping to real products

_Coming in Stage 5 (Microsoft Purview, Netskope, Zscaler, Varonis, and where this lab simplifies)._
