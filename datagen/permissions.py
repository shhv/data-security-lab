"""Mock identity directory + ACL model.

IAM analogy cheat-sheet:
- users[]          ≈ Entra/Okta user objects (SCIM-provisioned). `type: guest` ≈ Entra B2B guest.
- groups[]         ≈ security groups. `members` may contain other groups (nested groups), so
                     "who can read this?" requires transitive expansion - same as resolving
                     group claims in a SAML/OIDC token.
- acls{path: ...}  ≈ resource-side authorization (SharePoint/Drive/Blob ACLs). Grants on a
                     container are INHERITED by everything under it unless a child sets
                     `inherit: false` (SharePoint "stop inheriting permissions").
- principal kinds:
    user:<id>          a single identity
    group:<id>         expand transitively
    domain:<domain>    "anyone in the org" sharing link (authenticated, but very broad)
    anyone_with_link   UNAUTHENTICATED - the bearer-token of file sharing. No identity at all.

Note what's missing on purpose: no IdP, no tokens. DSPM tools don't authenticate as
users either - they read ACLs from the storage API and compute *potential* access.
"""

from __future__ import annotations

from datetime import date

from .fakes import PARTNER_DOMAIN, PERSONAL_DOMAIN, TENANT_DOMAIN, Faker

# (user_id, department) - names/emails are generated from the seed.
MEMBERS = [
    ("u01", "hr"), ("u02", "hr"),
    ("u03", "finance"), ("u04", "finance"), ("u05", "finance"),
    ("u06", "clinical"), ("u07", "clinical"),
    ("u08", "engineering"), ("u09", "engineering"), ("u10", "engineering"),
    ("u11", "marketing"), ("u12", "support"), ("u13", "support"),
]


def grant(principal: str, role: str = "reader", created: str = "2026-01-15",
          expires: str | None = None, created_by: str | None = None) -> dict:
    g = {"principal": principal, "role": role, "created": created}
    if expires:
        g["expires"] = expires
    if created_by:
        g["created_by"] = created_by
    return g


def build_directory(fk: Faker) -> dict:
    users = []
    for uid, dept in MEMBERS:
        first, last = fk.name()
        users.append({
            "id": uid, "upn": fk.email(first, last), "display_name": f"{first} {last}",
            "department": dept, "type": "member", "enabled": True,
            "last_sign_in": fk.date_between(date(2026, 9, 1), date(2026, 11, 13)).isoformat(),
        })

    # A leaver whose account was disabled but never removed from groups (classic JML gap).
    first, last = fk.name()
    users.append({
        "id": "u14", "upn": fk.email(first, last), "display_name": f"{first} {last}",
        "department": "finance", "type": "member", "enabled": False,
        "last_sign_in": "2025-12-02",
    })

    # External guests (B2B). UPN mimics Entra's #EXT# format.
    for gid, domain in [("g01", PARTNER_DOMAIN), ("g02", PERSONAL_DOMAIN)]:
        first, last = fk.name()
        ext = fk.email(first, last, domain)
        users.append({
            "id": gid, "upn": ext.replace("@", "_") + f"#EXT#@{TENANT_DOMAIN}",
            "external_email": ext, "display_name": f"{first} {last} (Guest)",
            "department": None, "type": "guest", "enabled": True,
            "last_sign_in": "2026-06-20",
        })

    def dept(d: str) -> list[str]:
        return [u["id"] for u in users if u["department"] == d and u["type"] == "member"]

    groups = [
        {"id": "grp-hr", "name": "HR Team", "members": dept("hr")},
        {"id": "grp-finance-leads", "name": "Finance Leads", "members": ["u03"]},
        # Nested group: finance includes finance-leads.
        {"id": "grp-finance", "name": "Finance Team",
         "members": dept("finance") + ["grp-finance-leads"]},
        {"id": "grp-clinical", "name": "Clinical Staff", "members": dept("clinical")},
        {"id": "grp-engineering", "name": "Engineering", "members": dept("engineering")},
        {"id": "grp-marketing", "name": "Marketing", "members": dept("marketing")},
        {"id": "grp-support", "name": "Support", "members": dept("support")},
        {"id": "grp-contractors", "name": "Contractors", "members": ["u10", "g01"]},
        # "All Employees" style group: every member user (dynamic group in Entra terms).
        {"id": "grp-all-employees", "name": "All Employees",
         "members": [u["id"] for u in users if u["type"] == "member"]},
        # SharePoint's "Everyone" claim includes guests - a frequent oversharing culprit.
        {"id": "grp-everyone", "name": "Everyone (incl. guests)",
         "members": ["grp-all-employees", "g01", "g02"]},
        # Nested two levels deep, which pulls a guest into engineering data.
        {"id": "grp-eng-extended", "name": "Engineering Extended",
         "members": ["grp-engineering", "grp-contractors"]},
    ]
    return {"tenant": TENANT_DOMAIN, "users": users, "groups": groups}


def container_acls(owner_by_container: dict[str, str]) -> dict[str, dict]:
    """Baseline ACLs at the container ("site"/"bucket"/"shared drive") level.
    Mostly least-privilege; the interesting mistakes are added per file in generate.py."""
    base = {
        "hr-share": [grant("group:grp-hr", "writer")],
        "finance": [grant("group:grp-finance", "writer")],
        "clinical": [grant("group:grp-clinical", "writer")],
        "engineering": [grant("group:grp-eng-extended", "writer")],
        "marketing": [grant("group:grp-marketing", "writer"),
                      grant("group:grp-all-employees", "reader")],
        "support": [grant("group:grp-support", "writer")],
        "shared-drive": [],  # personal folders: owner-only unless shared
    }
    return {
        c: {"owner": owner_by_container[c], "inherit": True, "grants": grants}
        for c, grants in base.items()
    }
