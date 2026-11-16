-- Answers for docs/SQL_EXERCISES.md. Try each exercise yourself first!
-- Run one:   sqlite3 -init .sqliterc.lab lab_data/lab.db   then paste the query
-- Run all:   sqlite3 -init .sqliterc.lab lab_data/lab.db < docs/sql_answers.sql
-- "Today" in the lab is fixed at 2026-11-14 so answers don't change over time.

-- ===================== EASY =====================
.print '--- E1'
SELECT * FROM users;

.print '--- E2'
SELECT upn, last_sign_in FROM users
WHERE department = 'finance'
ORDER BY last_sign_in DESC;

.print '--- E3'
SELECT display_name, upn FROM users WHERE type = 'guest';

.print '--- E4'
SELECT path FROM files WHERE container = 'finance';

.print '--- E5'
SELECT path, credit_card FROM files WHERE credit_card > 0 ORDER BY credit_card DESC;

.print '--- E6'
SELECT path, created_by, created FROM grants WHERE principal_kind = 'anyone_with_link';

.print '--- E7'
SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department;

.print '--- E8'
SELECT id, upn, last_sign_in FROM users WHERE last_sign_in < '2026-10-01';

.print '--- E9'
SELECT path FROM files WHERE path LIKE '%.csv';

.print '--- E10'
SELECT path, principal, expires FROM grants WHERE expires IS NOT NULL;

-- ===================== MEDIUM =====================
.print '--- M1'
SELECT department, COUNT(*) AS users
FROM users WHERE department IS NOT NULL
GROUP BY department ORDER BY users DESC;

.print '--- M2'
SELECT container, SUM(ssn) AS ssns
FROM files GROUP BY container
ORDER BY ssns DESC;

.print '--- M3'
SELECT container, COUNT(*) AS n FROM files
GROUP BY container HAVING COUNT(*) > 2;

.print '--- M4'
SELECT f.path, u.display_name AS owner
FROM files f JOIN users u ON f.owner = u.id;

.print '--- M5'
SELECT f.path, u.display_name, u.last_sign_in
FROM files f JOIN users u ON f.owner = u.id
WHERE u.enabled = 0;

.print '--- M6'
SELECT gr.path, g.name AS group_name, gr.role
FROM grants gr JOIN groups g ON gr.principal_ref = g.id
WHERE gr.principal_kind = 'group';

.print '--- M7'
SELECT g.name, u.display_name AS guest
FROM group_members gm
JOIN groups g ON gm.group_id = g.id
JOIN users  u ON gm.member_id = u.id
WHERE u.type = 'guest';

.print '--- M8'
SELECT f.path
FROM files f LEFT JOIN grants gr ON gr.path = f.path
WHERE gr.path IS NULL;

.print '--- M9'
SELECT f.path, f.ssn, f.credit_card, f.email
FROM files f JOIN grants gr ON gr.path = f.path
WHERE gr.principal_kind = 'anyone_with_link' AND f.sensitive = 1;

.print '--- M10'
SELECT principal_kind, COUNT(*) AS grants
FROM grants GROUP BY principal_kind ORDER BY grants DESC;

-- ===================== HARD =====================
.print '--- H1  expand nested groups: every user in grp-everyone, at any depth'
WITH RECURSIVE expand(member_id, depth) AS (
  SELECT member_id, 1 FROM group_members WHERE group_id = 'grp-everyone'
  UNION
  SELECT gm.member_id, e.depth + 1
  FROM expand e JOIN group_members gm ON gm.group_id = e.member_id
)
SELECT DISTINCT u.id, u.display_name, u.type
FROM expand e JOIN users u ON u.id = e.member_id
ORDER BY u.type, u.id;

.print '--- H2  every group that contains a guest at any depth (and the path)'
WITH RECURSIVE chain(top_group, member_id, path) AS (
  SELECT group_id, member_id, group_id || ' > ' || member_id FROM group_members
  UNION ALL
  SELECT c.top_group, gm.member_id, c.path || ' > ' || gm.member_id
  FROM chain c JOIN group_members gm ON gm.group_id = c.member_id
)
SELECT c.top_group, c.path
FROM chain c JOIN users u ON u.id = c.member_id
WHERE u.type = 'guest'
ORDER BY c.top_group;

.print '--- H3  effective grants: file-level grants + inherited container grants'
WITH effective AS (
  SELECT f.path, gr.principal, gr.role, 'direct' AS source
  FROM files f JOIN grants gr ON gr.path = f.path
  UNION ALL
  SELECT f.path, gr.principal, gr.role, 'inherited from ' || f.container
  FROM files f JOIN grants gr ON gr.path = f.container
  WHERE f.inherit = 1
)
SELECT * FROM effective ORDER BY path;

.print '--- H4  which guests can reach engineering/app log (nesting + inheritance)'
WITH RECURSIVE
principals AS (               -- groups granted on the file or (inherited) its container
  SELECT gr.principal_ref AS id
  FROM files f JOIN grants gr ON gr.path IN (f.path, CASE WHEN f.inherit = 1 THEN f.container END)
  WHERE f.path = 'engineering/logs/app_2026-11.log' AND gr.principal_kind IN ('group','user')
),
expand(id) AS (
  SELECT id FROM principals
  UNION
  SELECT gm.member_id FROM expand e JOIN group_members gm ON gm.group_id = e.id
)
SELECT u.id, u.display_name FROM expand e JOIN users u ON u.id = e.id WHERE u.type = 'guest';

.print '--- H5  stale files (not accessed in 365 days before 2026-11-14)'
SELECT path, last_accessed,
       CAST(julianday('2026-11-14') - julianday(last_accessed) AS INTEGER) AS days_idle
FROM files
WHERE last_accessed < date('2026-11-14', '-365 days')
ORDER BY days_idle DESC;

.print '--- H6  expired grants that still exist'
SELECT path, principal, expires,
       CASE WHEN expires < '2026-11-14' THEN 'EXPIRED - remove' ELSE 'active' END AS status
FROM grants WHERE expires IS NOT NULL;

.print '--- H7  exposure score per sensitive file'
WITH flags AS (
  SELECT f.path, f.ssn + f.credit_card + f.email + f.health_record AS values_found,
    MAX(CASE WHEN gr.principal_kind = 'anyone_with_link' THEN 1 ELSE 0 END) AS public_link,
    MAX(CASE WHEN gr.principal_kind = 'domain'
              OR gr.principal_ref IN ('grp-everyone','grp-all-employees') THEN 1 ELSE 0 END) AS broad,
    MAX(CASE WHEN u.type = 'guest' THEN 1 ELSE 0 END) AS direct_guest,
    MAX(CASE WHEN f.last_accessed < date('2026-11-14','-365 days') THEN 1 ELSE 0 END) AS stale
  FROM files f
  LEFT JOIN grants gr ON gr.path = f.path
  LEFT JOIN users u ON gr.principal_kind = 'user' AND u.id = gr.principal_ref
  WHERE f.sensitive = 1
  GROUP BY f.path
)
SELECT path, values_found, public_link, broad, direct_guest, stale,
       3*public_link + 2*broad + 2*direct_guest + stale AS score
FROM flags ORDER BY score DESC, values_found DESC;

.print '--- H8  rank files by sensitive values within each container (window function)'
SELECT container, path,
       ssn + credit_card + email + health_record AS total,
       RANK() OVER (PARTITION BY container ORDER BY ssn + credit_card + email + health_record DESC) AS rnk
FROM files ORDER BY container, rnk;

.print '--- H9  masked access-review view (show only last 4 chars of the UPN local part)'
DROP VIEW IF EXISTS v_owner_review;
CREATE TEMP VIEW v_owner_review AS
SELECT f.path, '***' || substr(u.upn, instr(u.upn,'@') - 4, 4) || substr(u.upn, instr(u.upn,'@')) AS owner_masked,
       u.enabled, f.sensitive
FROM files f JOIN users u ON u.id = f.owner;
SELECT * FROM v_owner_review WHERE sensitive = 1 LIMIT 5;

.print '--- H10 SQL injection: these are the SAME query; only one is safe from Python'
-- unsafe (Python):  cur.execute(f"SELECT * FROM users WHERE upn = '{x}'")
--   with x = "' OR '1'='1"  ->  WHERE upn = '' OR '1'='1'   returns EVERY user:
SELECT COUNT(*) AS rows_leaked FROM users WHERE upn = '' OR '1'='1';
-- safe (Python):    cur.execute("SELECT * FROM users WHERE upn = ?", (x,))  -> 0 rows
