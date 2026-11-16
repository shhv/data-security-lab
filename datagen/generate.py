"""Build the lab: storage tree + permissions.json + manifest.json.

Output layout (mimics one cloud storage account with several containers/sites/buckets):

    <out>/
      storage/acmeprodstorage/<container>/<path>   the files
      permissions.json                             directory (users, groups) + ACLs
      manifest.json                                ground truth per file (answer key)

Each FileSpec can add file-level grants (oversharing incidents) and can break
inheritance. The incidents are deliberately realistic - each one maps to a finding
a real DSPM tool would raise in Stage 3.
"""

from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import content as c
from . import evalset
from .fakes import TENANT_DOMAIN, Faker
from .permissions import build_directory, container_acls, grant

ACCOUNT = "acmeprodstorage"


@dataclass
class FileSpec:
    path: str                                   # "<container>/<rest>"
    build: Callable[[Faker], c.Built]
    owner: str
    last_modified: str = "2026-10-20"
    last_accessed: str = "2026-11-10"
    grants: list[dict] = field(default_factory=list)  # added on top of inherited grants
    inherit: bool = True
    note: str = ""                              # why this file is interesting (for learners)


def layout() -> list[FileSpec]:
    return [
        # --- HR ---------------------------------------------------------------
        FileSpec("hr-share/employees/roster.csv", c.hr_roster, "u01"),
        FileSpec("hr-share/payroll/2026-10_payroll.csv", c.payroll, "u02",
                 grants=[grant("group:grp-everyone", "reader", "2026-10-31", created_by="u02")],
                 note="Shared with 'Everyone' - which silently includes guests."),
        FileSpec("hr-share/benefits/open_enrollment_faq.txt", lambda fk: c.clean_text("faq"), "u01"),
        FileSpec("hr-share/terminations/2024_offboarding.csv", lambda fk: c.hr_roster(fk, 6), "u14",
                 last_modified="2024-03-02", last_accessed="2024-04-11",
                 note="Stale, and owned by a disabled account (orphaned data)."),
        # --- Finance ----------------------------------------------------------
        FileSpec("finance/payments/transactions_2026-10.csv", c.transactions, "u03",
                 inherit=False, grants=[grant("group:grp-finance-leads", "writer")],
                 note="Good example: inheritance broken to least privilege."),
        FileSpec("finance/payments/invoice_refs.txt", c.invoice_numbers, "u04",
                 note="Decoys only: 16-digit IDs that fail Luhn."),
        FileSpec("finance/reports/q3_summary.txt", lambda fk: c.clean_text("q3"), "u05"),
        # --- Support ----------------------------------------------------------
        FileSpec("support/tickets/ticket_1042.txt", lambda fk: c.support_ticket(fk, 1042, True), "u12",
                 grants=[grant("anyone_with_link", "reader", "2026-09-14", created_by="u12")],
                 note="Customer pasted a card number; ticket shared via public link."),
        FileSpec("support/tickets/ticket_1043.txt", lambda fk: c.support_ticket(fk, 1043, False), "u13"),
        # --- Marketing --------------------------------------------------------
        FileSpec("marketing/campaigns/newsletter_list.csv", c.newsletter_list, "u11",
                 grants=[grant("anyone_with_link", "reader", "2026-08-01", created_by="u11")],
                 note="Public link, but only emails: lower severity than cards/SSNs."),
        FileSpec("marketing/public/press_release.txt", lambda fk: c.clean_text("press"), "u11",
                 grants=[grant("anyone_with_link", "reader")],
                 note="Public on purpose and harmless: exposure alone is not a finding."),
        # --- Engineering ------------------------------------------------------
        FileSpec("engineering/logs/app_2026-11.log", c.app_log, "u08",
                 note="Container ACL -> grp-eng-extended -> grp-contractors -> guest g01."),
        FileSpec("engineering/docs/service_design.md", lambda fk: c.clean_text("design"), "u09"),
        # --- Clinical ---------------------------------------------------------
        FileSpec("clinical/patients/records.json", c.patient_records, "u06"),
        FileSpec("clinical/exports/partner_referrals.csv", c.partner_export, "u07",
                 grants=[grant("user:g01", "reader", "2026-06-18", expires="2026-07-18", created_by="u07")],
                 note="Shared with external guest; the grant's expiry date has passed."),
        # --- Personal / shared drive -------------------------------------------
        FileSpec("shared-drive/u08/debug_notes.txt", c.dev_notes, "u08",
                 grants=[grant("anyone_with_link", "reader", "2026-05-03", created_by="u08")],
                 note="Shadow data: prod PII copied into a personal note, then link-shared."),
        FileSpec("shared-drive/u04/budget_2022.csv", c.old_budget, "u04",
                 last_modified="2022-11-30", last_accessed="2023-01-09",
                 grants=[grant(f"domain:{TENANT_DOMAIN}", "reader", "2022-12-01", created_by="u04")],
                 note="Stale + org-wide link + card numbers."),
    ]


def _ts(day: str) -> float:
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()


def generate(out: Path, seed: int = 42, clean: bool = True) -> dict:
    out = Path(out)
    if clean and out.exists():
        shutil.rmtree(out)
    root = out / "storage" / ACCOUNT
    fk = Faker(seed)

    directory = build_directory(fk)
    specs = layout()
    containers = sorted({s.path.split("/")[0] for s in specs})
    owners = {cname: next(s.owner for s in specs if s.path.startswith(cname + "/")) for cname in containers}
    acls = container_acls(owners)
    manifest: dict[str, dict] = {}
    totals: Counter = Counter()

    for spec in specs:
        text, truth = spec.build(fk)
        dest = root / spec.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        # atime/mtime on disk mirror the metadata, so a scanner can use either.
        os.utime(dest, (_ts(spec.last_accessed), _ts(spec.last_modified)))

        acls[spec.path] = {"owner": spec.owner, "inherit": spec.inherit, "grants": spec.grants,
                           "last_modified": spec.last_modified, "last_accessed": spec.last_accessed}
        manifest[spec.path] = {"truth": dict(truth), "sensitive": any(
            truth[k] for k in ("ssn", "credit_card", "email", "health_record")), "note": spec.note}
        totals.update(truth)

    perms = {**directory, "storage_account": ACCOUNT, "acls": acls}
    (out / "permissions.json").write_text(json.dumps(perms, indent=2) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(
        {"seed": seed, "account": ACCOUNT, "totals": dict(totals), "files": manifest}, indent=2) + "\n",
        encoding="utf-8")
    ev = evalset.write(out)  # labeled snippet set for classifier evaluation (Stage 6)
    return {"files": len(specs), "totals": dict(totals), "eval_set": ev, "out": str(out)}
