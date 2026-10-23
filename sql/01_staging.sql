-- STAGING: type, rename and union the two CMS releases, keep raw untouched.
CREATE OR REPLACE TABLE stg_phys AS
WITH src AS (
    SELECT 2023 AS service_year, * FROM read_csv('data/raw/MUP_PHY_R25_P05_V20_D23_Geo.csv', header=true, all_varchar=true)
    UNION ALL BY NAME
    SELECT 2024 AS service_year, * FROM read_csv('data/raw/MUP_PHY_R26_P05_V10_D24_Geo.csv', header=true, all_varchar=true)
)
SELECT
    service_year,
    Rndrng_Prvdr_Geo_Lvl                         AS geo_level,
    COALESCE(Rndrng_Prvdr_Geo_Cd, CASE WHEN Rndrng_Prvdr_Geo_Lvl='National' THEN '00' ELSE 'ZZ' END) AS state_fips,
    COALESCE(Rndrng_Prvdr_Geo_Desc, 'Unspecified (blank in source)') AS state_name,
    TRIM(HCPCS_Cd)                               AS hcpcs_cd,
    HCPCS_Desc                                   AS hcpcs_desc,
    HCPCS_Drug_Ind = 'Y'                         AS is_drug,
    Place_Of_Srvc                                AS pos_cd,
    CAST(Tot_Rndrng_Prvdrs AS BIGINT)            AS providers,
    CAST(Tot_Benes AS BIGINT)                    AS beneficiaries,
    CAST(Tot_Srvcs AS DOUBLE)                    AS services,
    CAST(Tot_Bene_Day_Srvcs AS DOUBLE)           AS bene_day_services,
    CAST(Avg_Sbmtd_Chrg AS DOUBLE)               AS avg_submitted,
    CAST(Avg_Mdcr_Alowd_Amt AS DOUBLE)           AS avg_allowed,
    CAST(Avg_Mdcr_Pymt_Amt AS DOUBLE)            AS avg_paid,
    CAST(Avg_Mdcr_Stdzd_Amt AS DOUBLE)           AS avg_standardized
FROM src;

CREATE OR REPLACE TABLE stg_enrollment AS
SELECT CAST(YEAR AS INT) AS enrol_year, BENE_STATE_ABRVTN AS state_abbr, BENE_STATE_DESC AS state_name,
       CAST(TRY_CAST(TOT_BENES AS DOUBLE) AS BIGINT)          AS total_benes,
       CAST(TRY_CAST(ORGNL_MDCR_BENES AS DOUBLE) AS BIGINT)   AS ffs_benes,
       CAST(TRY_CAST(B_ORGNL_MDCR_BENES AS DOUBLE) AS BIGINT) AS ffs_part_b_benes
FROM read_csv('data/raw/enrollment.csv', header=true, all_varchar=true)
WHERE BENE_GEO_LVL IN ('State','National') AND MONTH = 'Year' AND YEAR IN ('2023','2024');
