-- 00_discover_items.sql
-- Run this first and inspect the output. MIMIC-IV itemids can change between versions.
-- The pipeline uses the MetaVision CRRT itemids listed in 01_crrt_episodes.sql.

SELECT itemid, label, abbreviation, linksto, category, unitname
FROM `{{icu}}.d_items`
WHERE REGEXP_CONTAINS(LOWER(label), r'dialys|replacement|blood flow|cvvh|cvvhd|cvvhdf|crrt|renal replacement|hemodialys|ultrafiltr')
ORDER BY category, label;

-- Urine output candidates
SELECT itemid, label, category, unitname
FROM `{{icu}}.d_items`
WHERE REGEXP_CONTAINS(LOWER(label), r'urine|foley|void')
ORDER BY category, label;

-- Vasopressor candidates
SELECT itemid, label, category, unitname
FROM `{{icu}}.d_items`
WHERE REGEXP_CONTAINS(LOWER(label), r'norepinephrine|noradrenaline|vasopressin|phenylephrine|epinephrine|dopamine')
ORDER BY label;
