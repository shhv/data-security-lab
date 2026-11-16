# CLAUDE.md — Data Security Lab (DSPM + DLP)

## Goal
A hands-on lab for learning data security fundamentals, specifically
**DSPM** (Data Security Posture Management: *where is sensitive data and who can reach it?*)
and **DLP** (Data Loss Prevention: *should this specific data movement be allowed?*).

The learner has an identity/IAM background (SAML, OIDC, SCIM, Entra, Okta, Google
Workspace). Connect new concepts to identity ideas where it helps
(e.g. effective permissions ≈ group expansion, "anyone with link" ≈ unauthenticated access,
external guests ≈ B2B guest accounts, stale data ≈ stale accounts).

## Hard rules
- **All data is synthetic and fake.** Never use real PII, credentials, or company data.
  - SSNs: area 900–999 with group 01–49 — never issued as SSNs and outside ITIN ranges.
  - Credit cards: only publicly documented processor **test** PANs.
  - Emails/domains: only RFC 2606 reserved names (`*.example`, `example.com`, etc.).
- Python 3.11+, minimal dependencies (stdlib first; PyYAML for policies, pytest for tests).
- Runnable locally, no cloud accounts needed.
- Explain the **why** briefly while building, not just the what.
- Build in small stages. **Stop after each stage** so the learner can run and read the code.

## Layout
- `datagen/`  synthetic data generator + mock permissions model
- `dspm/`     scanner and classifier
- `dlp/`      policy engine and event simulator
- `policies/` YAML DLP policies
- `tests/`    pytest cases
- `README.md` concepts and mapping to real products

## Staged plan
- [x] **Stage 1 — datagen.** Mixed sensitive/non-sensitive files in a cloud-storage-like tree,
      a mock permissions model (users, groups, nested groups, "anyone with link", external
      guests), and a ground-truth manifest.
- [x] **Stage 2 — classifier.** Detect SSNs, credit cards (Luhn), emails. Compare regex-only,
      checksum, and keyword-context detection. Test set that shows false positives.
- [ ] **Stage 3 — DSPM scanner.** Where sensitive data lives, who can access it, exposure
      score (overshared, external, stale).
- [ ] **Stage 4 — DLP engine.** YAML policies: conditions (data type, count threshold,
      destination, user group); actions (allow, warn, block, require justification).
      Event simulator ("user uploads file to personal email").
- [ ] **Stage 5 — README mapping** to Microsoft Purview, Netskope, Zscaler, Varonis, and
      where the lab simplifies.
- [ ] **Stage 6 — LLM vs deterministic classification.** Optional, behind `--classifier llm`;
      default stays regex and the lab must work with no LLM and no API key.
      Steps (pause after each):
  1. [x] Common `Classifier` interface: `classify(text) -> list[Finding]`
         (type, span, confidence, explanation). Built directly into Stage 2.
  2. [x] Labeled eval set (~200 snippets) with hard cases: formats, FP bait, context-dependent,
         no-pattern (diagnosis/salary/address), obfuscated, non-English.
  3. [ ] LLM classifier: versioned prompt in `prompts/classify_v1.txt`, strict JSON, defensive
         parsing (malformed output = recorded error, not crash), tells model data is fake.
         Backends: hosted API + local Ollama. Key from env var only. Call cap (default 50),
         dry-run mode, disk cache keyed by hash(content + prompt version).
  4. [ ] `python -m eval.compare`: P/R/F1 per type + overall, FP/FN lists, latency, cost
         estimate, consistency (3 runs on subset). Markdown + CSV output.
  5. [ ] Hybrid cascade: deterministic first, LLM only for ambiguous/no-match. Accuracy vs cost.
  6. [ ] DLP engine selects classifier via config; policy tests where the choice changes outcome.
  7. [ ] README "Regex vs LLM vs Hybrid" + prompt-injection test file.

## LLM safety rules (Stage 6)
- Only synthetic lab data is ever sent to a model.
- API keys come from environment variables only; never hardcoded or committed. `.env` is gitignored.
- Any network-calling path must honor the call cap and dry-run mode and check the cache first.

## Learning mode
After each stage:
1. Give the learner **3 short questions** about the concepts in that stage.
2. Give **one small code change** for the learner to make themselves (with a hint and how
   to verify it, e.g. a test to run). Do not make that change for them.
3. Wait for answers before moving on. Ask one question at a time if the learner prefers.

## Commands
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m datagen --out lab_data --seed 42
.venv/bin/pytest -q
```
