-- KPI LAYER
CREATE OR REPLACE VIEW kpi_national_year AS
WITH n AS (
  SELECT service_year, SUM(services) services, SUM(submitted_amt) submitted, SUM(allowed_amt) allowed,
         SUM(paid_amt) paid, SUM(standardized_amt) standardized, COUNT(DISTINCT hcpcs_cd) hcpcs_codes
  FROM fct_service_national GROUP BY 1),
e AS (SELECT enrol_year service_year, ffs_part_b_benes FROM stg_enrollment WHERE state_abbr='US')
SELECT n.*, e.ffs_part_b_benes,
       paid / ffs_part_b_benes                      AS paid_per_ffs_b_bene,
       services / ffs_part_b_benes                  AS services_per_ffs_b_bene,
       paid / services                              AS paid_per_service,
       paid / allowed                               AS paid_to_allowed,
       submitted / allowed                          AS charge_to_allowed_markup,
       paid / LAG(paid) OVER (ORDER BY service_year) - 1 AS paid_yoy,
       services / LAG(services) OVER (ORDER BY service_year) - 1 AS services_yoy
FROM n JOIN e USING (service_year) ORDER BY 1;

CREATE OR REPLACE VIEW kpi_family_year AS
SELECT f.service_year, h.service_family, SUM(paid_amt) paid, SUM(services) services,
       SUM(paid_amt) / SUM(SUM(paid_amt)) OVER (PARTITION BY f.service_year) AS share_of_paid
FROM fct_service_national f JOIN dim_hcpcs h USING (hcpcs_cd) GROUP BY 1, 2 ORDER BY 1, 3 DESC;

CREATE OR REPLACE VIEW kpi_top_hcpcs AS
WITH x AS (
  SELECT f.service_year, f.hcpcs_cd, h.hcpcs_desc, h.service_family,
         SUM(paid_amt) paid, SUM(services) services, SUM(beneficiaries) benes_pos_sum
  FROM fct_service_national f JOIN dim_hcpcs h USING (hcpcs_cd) GROUP BY ALL),
r AS (
  SELECT *, RANK() OVER (PARTITION BY service_year ORDER BY paid DESC) AS paid_rank,
         paid / SUM(paid) OVER (PARTITION BY service_year) AS share_of_paid,
         SUM(paid) OVER (PARTITION BY service_year ORDER BY paid DESC ROWS UNBOUNDED PRECEDING)
           / SUM(paid) OVER (PARTITION BY service_year) AS cum_share
  FROM x)
SELECT r.*, r.paid / p.paid - 1 AS paid_yoy
FROM r LEFT JOIN x p ON p.hcpcs_cd = r.hcpcs_cd AND p.service_year = r.service_year - 1
ORDER BY service_year, paid_rank;

CREATE OR REPLACE VIEW kpi_state_year AS
SELECT f.service_year, d.state_fips, d.state_abbr, d.state_name,
       SUM(paid_amt) paid, SUM(standardized_amt) standardized, SUM(services) services,
       MAX(e.ffs_part_b_benes) AS ffs_part_b_benes,
       SUM(paid_amt) / MAX(e.ffs_part_b_benes)         AS paid_per_ffs_b_bene,
       SUM(standardized_amt) / MAX(e.ffs_part_b_benes) AS std_per_ffs_b_bene,
       SUM(services) / MAX(e.ffs_part_b_benes)         AS services_per_ffs_b_bene,
       SUM(paid_amt) / SUM(standardized_amt)      AS price_index
FROM fct_service f JOIN dim_state d USING (state_fips)
JOIN fct_enrollment e USING (state_fips, service_year)
WHERE d.state_group = '50 states + DC'
GROUP BY ALL ORDER BY 1, paid_per_ffs_b_bene DESC;

-- Utilisation outliers: for the top-100 national cost codes, services per 1,000 FFS Part B beneficiaries
-- by state, robust z-score (median/MAD on log rate) across the 51 jurisdictions.
CREATE OR REPLACE VIEW kpi_outliers AS
WITH top AS (SELECT hcpcs_cd FROM kpi_top_hcpcs WHERE service_year = 2024 AND paid_rank <= 100),
s AS (
  SELECT f.service_year, f.state_fips, d.state_abbr, f.hcpcs_cd,
         SUM(f.services) services, SUM(f.paid_amt) paid,
         1000 * SUM(f.services) / MAX(e.ffs_part_b_benes) AS svc_per_1k
  FROM fct_service f JOIN top USING (hcpcs_cd) JOIN dim_state d USING (state_fips)
  JOIN fct_enrollment e USING (state_fips, service_year)
  WHERE d.state_group = '50 states + DC' AND f.service_year = 2024 GROUP BY ALL),
m AS (SELECT hcpcs_cd, MEDIAN(LN(svc_per_1k)) med, COUNT(*) n_states FROM s GROUP BY 1),
mad AS (SELECT s.hcpcs_cd, MEDIAN(ABS(LN(svc_per_1k) - med)) mad FROM s JOIN m USING (hcpcs_cd) GROUP BY 1)
SELECT s.*, h.hcpcs_desc, h.service_family, m.n_states, EXP(m.med) AS median_svc_per_1k,
       svc_per_1k / EXP(m.med) AS ratio_to_median,
       0.6745 * (LN(svc_per_1k) - m.med) / NULLIF(mad.mad, 0) AS robust_z,
       ABS(0.6745 * (LN(svc_per_1k) - m.med) / NULLIF(mad.mad, 0)) > 3.5 AS is_outlier
FROM s JOIN m USING (hcpcs_cd) JOIN mad USING (hcpcs_cd) JOIN dim_hcpcs h USING (hcpcs_cd)
ORDER BY robust_z DESC;

CREATE OR REPLACE VIEW kpi_pos_year AS
SELECT service_year, p.pos_desc, SUM(paid_amt) paid, SUM(services) services, SUM(paid_amt)/SUM(services) paid_per_service
FROM fct_service_national JOIN dim_place_of_service p USING (pos_cd) GROUP BY ALL ORDER BY 1, 2;
