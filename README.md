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

## Setup and rebuilding the lab

Generated data is **not** committed. Everything under `lab_data/` is rebuilt from code, so a
fresh clone has none of it until you run the steps below.

### 1. First-time setup (once per clone)
```bash
git clone <repo-url> data-security-lab && cd data-security-lab
python3 -m venv .venv                       # Python 3.11+
.venv/bin/pip install -e ".[dev]"           # add ,llm for the optional hosted-LLM backend
```

### 2. Build the lab data
```bash
.venv/bin/python -m datagen                 # fake storage tree, permissions, manifest, eval set
.venv/bin/python -m sqllab.load             # SQLite practice DBs (needs step 2's output)
```
Run them in this order. **`datagen` wipes `lab_data/` first**, deleting the databases too, so
always run `sqllab.load` again after it.

### 3. Check it worked
```bash
.venv/bin/pytest -q                         # all tests should pass
.venv/bin/python -m dspm.compare_levels     # classifier comparison table
sqlite3 -init .sqliterc.lab lab_data/lab.db "SELECT COUNT(*) FROM files;"   # 17
```

### What gets generated

| Path | Made by | What it is |
|---|---|---|
| `lab_data/storage/acmeprodstorage/` | `datagen` | 17 fake files across 7 containers |
| `lab_data/permissions.json` | `datagen` | users, guests, nested groups, ACLs |
| `lab_data/manifest.json` | `datagen` | answer key: what was planted in each file |
| `lab_data/eval/snippets.jsonl`, `labels.jsonl` | `datagen` | 200 labeled snippets for classifier evaluation |
| `lab_data/lab.db` | `sqllab.load` | SQL practice: the storage lab as tables |
| `lab_data/iam.db` | `sqllab.load` | SQL practice: IAM audit scenario (~6k sign-ins) |

### Options and resets
- **Different data, same layout:** `python -m datagen --seed 7`. The same seed always gives identical data.
- **Other folder:** `python -m datagen --out my_lab`, then `python -m sqllab.load my_lab`.
- **Reset after editing files or breaking a database:** rerun step 2.
- **Never commit `lab_data/` or `.env`.** Both are in `.gitignore`.

## Command reference

Run everything from the repo root:
`cd /Users/shhv/Documents/DuoStuff/data-security-stuff`

### SQL practice (SQLite console)
`sqlite3` ships with macOS, so there's nothing to install. Build the databases first (step 2 above).

```bash
sqlite3 -init .sqliterc.lab lab_data/lab.db     # storage lab: users, groups, files, grants
sqlite3 -init .sqliterc.lab lab_data/iam.db     # IAM audit: employees, apps, sign_ins, ...
```
`-init .sqliterc.lab` turns on column headers and aligned output. Without it, results are hard to read.

Inside the console (you'll see a `sqlite>` prompt):

| Type | What it does |
|---|---|
| `.tables` | list tables |
| `.schema users` | show a table's columns and keys |
| `SELECT * FROM users LIMIT 5;` | look at some rows. **SQL must end with `;`** |
| `.mode line` / `.mode column` | one column per line (wide tables) / back to a table layout |
| `.read docs/sql_answers.sql` | run a whole SQL file |
| `.quit` (or Ctrl-D) | exit |

If you're stuck at a `...>` prompt, you forgot the `;`. Type `;` and press Enter.

Run a single query without opening the console:
```bash
sqlite3 -header -column lab_data/lab.db "SELECT id, type FROM users WHERE type = 'guest';"
```

Study material:

| File | What it is |
|---|---|
| `docs/SQL_STUDY_PLAN.md` | 6-week plan, each week tied to a security question |
| `docs/SQL_EXERCISES.md` | 30 exercises (easy / medium / hard) with expected row counts |
| `docs/sql_answers.sql` | answers. Try the exercise first! |
| `docs/sql_cheatsheet.html` | printable "when to use what" + live-debug playbook. Run `open docs/sql_cheatsheet.html`, then ⌘P |

### Classifiers (find sensitive data)
```bash
.venv/bin/python -m dspm.classify --text "SSN: 912-34-5678"             # classify a string
.venv/bin/python -m dspm.classify my_test.txt                           # a file
.venv/bin/python -m dspm.classify lab_data/storage                      # a whole folder
.venv/bin/python -m dspm.classify my_test.txt --classifier regex-only   # pick a layer
.venv/bin/python -m dspm.compare_levels                                 # all 3 layers vs the answer key
.venv/bin/python -m dspm.compare_levels --production-ssn-rules          # real-world SSN rules
```
Classifiers: `regex-only`, `regex-checksum`, `regex-context` (`regex` is the default and means `regex-context`).
Use only fake values when testing: SSNs starting with 9, card `4111 1111 1111 1111`, emails ending in `.example`.

### Evaluation (labeled snippet set)
```bash
.venv/bin/python -m eval.score                                   # precision/recall per type and category
.venv/bin/python -m eval.score --show fp                         # list false positives
.venv/bin/python -m eval.score --show fn --category obfuscated   # misses in one category
.venv/bin/python -m eval.score --classifier regex-only
```
Categories: `clean`, `formatted`, `fp_bait`, `context`, `no_pattern`, `obfuscated`, `non_english`.

### Tests
```bash
.venv/bin/pytest -q                              # everything
.venv/bin/pytest tests/test_classifiers.py -v    # false-positive gallery, one line per lesson
```

### Look at the generated data
```bash
find lab_data/storage -type f                                                  # list fake files
cat lab_data/storage/acmeprodstorage/shared-drive/u08/debug_notes.txt         # read one
python3 -m json.tool lab_data/manifest.json | less                           # answer key
```

### Local LLM (Stage 6, in progress)
```bash
ollama serve                 # start the server (leave running, or open the Ollama app)
ollama list                  # installed models (llama3.2, phi3)
```
The LLM classifier isn't built yet. Regex stays the default and the lab works without any LLM.

### Git: save to both GitHub accounts
```bash
git add -A && git commit -m "what I changed"
git push origin main     # work account  (shhv_cisco)
git push self main       # personal      (shhv)
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
