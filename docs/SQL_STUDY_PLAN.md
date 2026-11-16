# SQL Study Plan (for an IAM / data-security learner)

**Goal:** be comfortable writing the SQL that security work actually needs: access reviews,
finding overshared data, joining identities to resources, and reading DSPM/DLP exports.

**Setup:** SQLite. It ships with Python and macOS (`sqlite3` in Terminal), so there's nothing to install.
Practice data: this lab's `permissions.json` and `manifest.json` (all fake).

**Pace:** about 30–45 minutes a day, 5 days a week, for 6 weeks. Each week ends with a
"security question" you answer only in SQL.

---

## Week 1: Reading one table (`SELECT`, `WHERE`, `ORDER BY`)
- Concepts: tables, rows, columns; `SELECT`, `WHERE`, `AND/OR`, `LIKE`, `IN`, `IS NULL`,
  `ORDER BY`, `LIMIT`, `DISTINCT`.
- IAM link: a table is like a SCIM resource list; `WHERE` is a SCIM filter
  (`userName sw "a"` ≈ `WHERE upn LIKE 'a%'`).
- Practice: list all guest users; list disabled accounts; users whose last sign-in was before
  2026-10-01.
- **Security question:** *Which accounts are guests or disabled?*

## Week 2: Counting and grouping (`COUNT`, `GROUP BY`, `HAVING`)
- Concepts: `COUNT`, `SUM`, `AVG`, `MIN/MAX`, `GROUP BY`, `HAVING`, and `WHERE` vs `HAVING`.
- Practice: users per department; files per container; total SSNs planted per container.
- **Security question:** *Which containers hold the most sensitive values?*

## Week 3: Joins (the heart of access reviews)
- Concepts: `INNER JOIN`, `LEFT JOIN`, join keys, and anti-joins (`LEFT JOIN ... WHERE x IS NULL`).
- IAM link: joining `users` to `group_members` to `grants` is exactly how you answer
  "who has access to what". Anti-joins find orphans, like files owned by deleted users.
- Practice: every grant with the group's display name; groups with no members; files whose
  owner is disabled.
- **Security question:** *Which files are owned by disabled accounts (orphaned data)?*

## Week 4: Nested groups (subqueries, CTEs, recursion)
- Concepts: subqueries, `WITH` (CTEs), and `WITH RECURSIVE`.
- IAM link: transitive group membership is a recursive query. It's the same problem
  Entra solves when it computes a token's group claims.
- Practice: expand `grp-everyone` down to individual users; find every group that contains a guest
  at any depth.
- **Security question:** *Which guests can reach `engineering/` through nested groups?*

## Week 5: Shaping results (`CASE`, dates, window functions)
- Concepts: `CASE WHEN`, date functions (`julianday`, `date('now','-365 days')`),
  `ROW_NUMBER()`, `RANK()`, `COUNT(*) OVER (PARTITION BY ...)`.
- Practice: label files "stale" if not accessed in a year; rank containers by exposure;
  mark expired grants.
- **Security question:** *Build an exposure score per file:*
  public link = 3, guest access = 2, stale = 1, multiplied by "has sensitive data".

## Week 6: Writing data and thinking like a defender
- Concepts: `CREATE TABLE`, `INSERT`, `UPDATE`, `DELETE`, primary/foreign keys, indexes,
  views, and transactions.
- Security topics:
  - **SQL injection:** why `f"... WHERE upn = '{x}'"` is dangerous and parameters (`?`) are not.
    Compare it to the prompt-injection lesson in Stage 6.
  - **Least privilege:** read-only connections and views that hide sensitive columns.
  - **Data masking:** `substr(ssn, -4)` to show only the last 4 digits.
- **Security question:** *Create a view that shows the access review without exposing raw sensitive values.*

---

## Capstone (week 6 or 7)
One SQL file, `access_review.sql`, that produces a report. For each file it lists the
sensitive types present, everyone who can access it (with nested groups expanded), whether any of
them are guests or disabled, whether it's public or stale, and an exposure score. Then compare it with
the Python DSPM scanner from Stage 3. They should agree.

## How to study each session
1. Read one concept: about 10 minutes (SQLite docs or any beginner SQL tutorial).
2. Predict the result of a query, then run it.
3. Write two queries of your own without looking at examples.
4. Write down in `NOTES.md` one mistake you made and why it happened.

## Useful references
- SQLite language docs: sqlite.org/lang.html (especially `SELECT`, `WITH`, and window functions)
- SQLBolt or SQLZoo: free interactive exercises for weeks 1–3
- "Use The Index, Luke": for indexes in week 6
- OWASP "SQL Injection Prevention Cheat Sheet": for week 6

## Next step in the lab
A small loader, `python -m sqllab.load`, would turn `permissions.json` and `manifest.json` into
`lab_data/lab.db` with tables `users`, `groups`, `group_members`, `acls`, `grants`, and
`files`. That gives you real (fake) data to query from day 1. It isn't built yet; ask for it when
you're ready to start week 1.

## Getting started (built)
```bash
.venv/bin/python -m sqllab.load                      # rebuild lab_data/lab.db (rerun after datagen)
sqlite3 -init .sqliterc.lab lab_data/lab.db          # open the console with readable output
```
Inside the console: `.tables`, `.schema users`, and `.quit` to exit. End every SQL statement with `;`.

## Exercises
`docs/SQL_EXERCISES.md` has 30 graded exercises (10 easy, 10 medium, 10 hard) with expected row counts.
Answers are in `docs/sql_answers.sql`. Only look after you've tried an exercise.
Mapping: Easy = weeks 1–2, Medium = weeks 2–3, Hard = weeks 4–6.
