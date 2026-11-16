# SQL Exercises: Easy, Medium, Hard

All exercises use `lab_data/lab.db`, which holds the lab's fake data.

```bash
sqlite3 -init .sqliterc.lab lab_data/lab.db
```

**How to work through them**
- Write the query yourself, run it, and only then check `docs/sql_answers.sql`.
- Before you run each query, guess how many rows it returns. Each one lists the expected count.
- "Today" in this lab is **2026-11-14**. Use that fixed date instead of `date('now')` so your answers match.
- If you break the database, `.venv/bin/python -m sqllab.load` rebuilds it.

**Tables:** `users`, `groups`, `group_members`, `files`, `grants`. Type `.schema` to see their columns.

---

## Easy: one table (`SELECT`, `WHERE`, `ORDER BY`)

| # | Question | Expected rows | Hint |
|---|---|---|---|
| E1 | Show every column of every user. | 16 | `*` |
| E2 | `upn` and `last_sign_in` of every **finance** user, newest sign-in first. | 4 | `ORDER BY ... DESC` |
| E3 | Name and UPN of every **guest** user. | 2 | `type` column |
| E4 | Every file in the `finance` container. | 3 | |
| E5 | Files containing at least one credit card number, most cards first. | 4 | `credit_card > 0` |
| E6 | Files shared with **anyone with the link**: path, who created the link, and when. | 4 | `principal_kind` |
| E7 | Each department name once, alphabetically, with no NULL. | 6 | `DISTINCT`, `IS NOT NULL` |
| E8 | Users who haven't signed in since before **2026-10-01**. | 7 | Dates are text in `YYYY-MM-DD` form, so `<` works |
| E9 | Every `.csv` file. | 7 | `LIKE '%.csv'` |
| E10 | Grants that have an expiry date. | 1 | `IS NOT NULL` |

**Think about it:** E8 returns two guests and one disabled user. Which kind of review would act on each?

---

## Medium: counting and joining (`GROUP BY`, `HAVING`, `JOIN`)

| # | Question | Expected rows | Hint |
|---|---|---|---|
| M1 | How many users per department, largest first? | 6 | `GROUP BY department` |
| M2 | Total SSNs per container, most first. | 7 | `SUM(ssn)` |
| M3 | Containers holding **more than 2** files. | 2 | `HAVING`, not `WHERE` |
| M4 | Each file's path with its owner's **display name**. | 17 | `JOIN users ON files.owner = users.id` |
| M5 | **Orphaned data:** files owned by a *disabled* account. | 1 | M4 plus `WHERE` |
| M6 | Every grant to a **group**, showing the group's name instead of its id. | 9 | Join `grants.principal_ref` to `groups.id` |
| M7 | Which groups have a guest as a **direct** member? | 3 | Two joins on `group_members` |
| M8 | Files with **no file-level grant**. | 9 | `LEFT JOIN ... WHERE grants.path IS NULL` |
| M9 | **Sensitive** files shared by public link, with their SSN, card and email counts. | 3 | Join plus two conditions |
| M10 | How many grants of each `principal_kind`? | 4 | |

**Think about it:**
- **M8:** the 9 files have no file-level grant, but are they private? Look at `grants` rows whose `path` is a container name like `hr-share`. (Answered in H3.)
- **M7:** it finds 3 group memberships. Is Engineering Extended missing from the list? Why? (Answered in H2.)

---

## Hard: recursion, inheritance, scoring, windows

| # | Question | Expected rows | Hint |
|---|---|---|---|
| H1 | **Expand nested groups:** every *user* in `grp-everyone` at any depth. | 16 | `WITH RECURSIVE`; start from the group's direct members, then repeatedly join `group_members` |
| H2 | Every group that contains a guest **at any depth**, and the chain that leads to them (e.g. `grp-eng-extended > grp-contractors > g01`). | 4 | Carry a text column through the recursion: `path \|\| ' > ' \|\| member_id` |
| H3 | **Effective grants:** for every file, its own grants **plus** its container's grants when `inherit = 1`, labelled `direct` or `inherited`. | 24 | `UNION ALL` of two joins |
| H4 | Which **guests** can reach `engineering/logs/app_2026-11.log`? | 1 | Combine H3 (inheritance) with H1 (nesting) |
| H5 | **Stale files:** not accessed in 365 days. Show the days idle. | 2 | `julianday()`, `date('2026-11-14','-365 days')` |
| H6 | Grants whose expiry date has passed but **still exist**. Label them with `CASE`. | 1 | `CASE WHEN expires < '2026-11-14'` |
| H7 | **Exposure score** for each sensitive file: public link = 3, broad group (`grp-everyone`, `grp-all-employees` or `domain:`) = 2, direct guest grant = 2, stale = 1. Highest first. | 12 | `MAX(CASE ...)` per flag, then `GROUP BY path` |
| H8 | Rank files by number of sensitive values **within each container**. | 17 | `RANK() OVER (PARTITION BY container ORDER BY ...)` |
| H9 | Create a **view** for an access review that shows each owner's UPN masked, like `***ey18@acme.example`. | 5 sensitive rows with `LIMIT 5` | `CREATE TEMP VIEW`, `substr`, `instr` |
| H10 | **SQL injection:** write the query that results when `x = ' OR '1'='1` is pasted into `WHERE upn = '{x}'`. How many rows leak? | 1 (count = 16) | Write out the string by hand |

**Think about it**
- **H7 has a flaw on purpose.** Its score gives `engineering/logs/app_2026-11.log` a 0, but H4 proves a guest can read that file. What is H7 missing? Fix it by reusing H3 and H1. That makes the query a small DSPM scanner, which is Stage 3 of the lab.
- **H10:** why does `cur.execute("... WHERE upn = ?", (x,))` return 0 rows for the same input? How does this compare to prompt injection against the LLM classifier?

---

## Boss level (optional)
Write **one** query that, for every sensitive file, lists:
- every *user* who can read it, after inheritance **and** nesting are resolved
- whether that user is a guest or disabled

Then count users per file. You've just written an access review report, the core of a DSPM tool.
