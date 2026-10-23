-- STAR SCHEMA: grain of fct_service = year x state x HCPCS x place of service (State level rows only).
CREATE OR REPLACE TABLE dim_year AS SELECT DISTINCT service_year FROM stg_phys ORDER BY 1;

CREATE OR REPLACE TABLE dim_place_of_service AS
SELECT * FROM (VALUES ('F','Facility'),('O','Office / non-facility')) t(pos_cd, pos_desc);

CREATE OR REPLACE TABLE dim_state AS
WITH s AS (SELECT DISTINCT state_fips, state_name FROM stg_phys WHERE geo_level='State')
SELECT s.state_fips, s.state_name, e.state_abbr,
       CASE WHEN e.state_abbr IS NOT NULL AND s.state_fips < '57' THEN '50 states + DC'
            WHEN s.state_fips IN ('60','66','69','72','78') THEN 'Territory'
            ELSE 'Other / unknown' END AS state_group
FROM s LEFT JOIN (SELECT DISTINCT state_abbr, state_name FROM stg_enrollment) e USING (state_name);

CREATE OR REPLACE TABLE dim_hcpcs AS
WITH ranked AS (
    SELECT hcpcs_cd, hcpcs_desc, is_drug,
           ROW_NUMBER() OVER (PARTITION BY hcpcs_cd ORDER BY service_year DESC, geo_level) AS rn
    FROM stg_phys)
SELECT hcpcs_cd, hcpcs_desc, is_drug,
    CASE
      WHEN is_drug                                         THEN 'Part B drugs'
      WHEN regexp_matches(hcpcs_cd, '^99[2-4][0-9]{2}$')   THEN 'Evaluation & management'
      WHEN regexp_matches(hcpcs_cd, '^[0-9]{4}[0-9]$') AND hcpcs_cd < '70000' THEN 'Surgery, procedures & anesthesia'
      WHEN regexp_matches(hcpcs_cd, '^7[0-9]{4}$')         THEN 'Radiology'
      WHEN regexp_matches(hcpcs_cd, '^8[0-9]{4}$')         THEN 'Lab & pathology'
      WHEN regexp_matches(hcpcs_cd, '^9[0-9]{4}$')         THEN 'Medicine (other)'
      WHEN regexp_matches(hcpcs_cd, '^[0-9]{4}[A-Z]$')     THEN 'Category II/III & PLA codes'
      ELSE 'HCPCS Level II (non-drug)' END AS service_family
FROM ranked WHERE rn = 1;

CREATE OR REPLACE TABLE fct_service AS
SELECT service_year, state_fips, hcpcs_cd, pos_cd,
       providers, beneficiaries, services, bene_day_services,
       ROUND(services * avg_submitted, 2)    AS submitted_amt,
       ROUND(services * avg_allowed, 2)      AS allowed_amt,
       ROUND(services * avg_paid, 2)         AS paid_amt,
       ROUND(services * avg_standardized, 2) AS standardized_amt
FROM stg_phys WHERE geo_level = 'State';

-- National rows kept separately: they include services suppressed at state level (<11 beneficiaries).
CREATE OR REPLACE TABLE fct_service_national AS
SELECT service_year, hcpcs_cd, pos_cd, providers, beneficiaries, services,
       ROUND(services * avg_submitted, 2) AS submitted_amt, ROUND(services * avg_allowed, 2) AS allowed_amt,
       ROUND(services * avg_paid, 2) AS paid_amt, ROUND(services * avg_standardized, 2) AS standardized_amt
FROM stg_phys WHERE geo_level = 'National';

CREATE OR REPLACE TABLE fct_enrollment AS
SELECT d.state_fips, e.enrol_year AS service_year, e.total_benes, e.ffs_benes, e.ffs_part_b_benes
FROM stg_enrollment e JOIN dim_state d USING (state_abbr);
