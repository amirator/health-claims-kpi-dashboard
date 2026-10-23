"""Run the layered DuckDB SQL, then export kpis.json, Power BI and Tableau files."""
import json, pathlib, duckdb

DB = "data/claims.duckdb"


def build():
    pathlib.Path(DB).unlink(missing_ok=True)
    con = duckdb.connect(DB)
    for f in sorted(pathlib.Path("sql").glob("*.sql")):
        con.execute(f.read_text())
    return con


def q(con, sql):
    return con.sql(sql).df()


def export_kpis(con):
    nat = q(con, "SELECT * FROM kpi_national_year").set_index("service_year")
    n24, n23 = nat.loc[2024], nat.loc[2023]
    top = q(con, "SELECT * FROM kpi_top_hcpcs WHERE service_year=2024 ORDER BY paid_rank LIMIT 10")
    top_all = q(con, "SELECT * FROM kpi_top_hcpcs WHERE service_year=2024")
    n_codes_80 = int((top_all.cum_share < 0.8).sum() + 1)
    fam = q(con, "SELECT * FROM kpi_family_year WHERE service_year=2024")
    st = q(con, "SELECT * FROM kpi_state_year WHERE service_year=2024 ORDER BY paid_per_ffs_b_bene DESC")
    out = q(con, "SELECT * FROM kpi_outliers WHERE is_outlier")
    grow = q(con, """SELECT * FROM kpi_top_hcpcs WHERE service_year=2024 AND paid_rank<=50
                     AND paid_yoy IS NOT NULL ORDER BY paid*paid_yoy/(1+paid_yoy) DESC LIMIT 5""")
    drug = fam.set_index("service_family").loc["Part B drugs"]
    hi, lo = st.iloc[0], st.iloc[-1]
    stdsort = st.sort_values("std_per_ffs_b_bene")
    k = {
        "paid_2024": n24.paid, "paid_2023": n23.paid, "paid_yoy": n24.paid_yoy,
        "allowed_2024": n24.allowed, "submitted_2024": n24.submitted,
        "services_2024": n24.services, "services_yoy": n24.services_yoy,
        "ffs_part_b_benes_2024": int(n24.ffs_part_b_benes),
        "paid_per_ffs_b_bene_2024": n24.paid_per_ffs_b_bene, "paid_per_ffs_b_bene_2023": n23.paid_per_ffs_b_bene,
        "paid_per_service_2024": n24.paid_per_service, "paid_to_allowed_2024": n24.paid_to_allowed,
        "charge_to_allowed_2024": n24.charge_to_allowed_markup, "hcpcs_codes_2024": int(n24.hcpcs_codes),
        "codes_for_80pct_paid": n_codes_80,
        "top10_share": float(top.share_of_paid.sum()),
        "top_code": {"code": top.hcpcs_cd[0], "desc": top.hcpcs_desc[0], "paid": top.paid[0], "share": top.share_of_paid[0]},
        "drug_share": drug.share_of_paid, "drug_paid": drug.paid,
        "state_high": {"name": hi.state_name, "value": hi.paid_per_ffs_b_bene},
        "state_low": {"name": lo.state_name, "value": lo.paid_per_ffs_b_bene},
        "state_ratio": hi.paid_per_ffs_b_bene / lo.paid_per_ffs_b_bene,
        "std_ratio": stdsort.std_per_ffs_b_bene.iloc[-1] / stdsort.std_per_ffs_b_bene.iloc[0],
        "std_high": stdsort.state_name.iloc[-1], "std_low": stdsort.state_name.iloc[0],
        "outlier_cells": len(out), "outlier_codes": int(out.hcpcs_cd.nunique()),
        "top_outlier": out.iloc[0][["state_abbr", "hcpcs_cd", "hcpcs_desc", "ratio_to_median", "robust_z"]].to_dict(),
        "top_growth": grow[["hcpcs_cd", "hcpcs_desc", "paid", "paid_yoy"]].to_dict("records"),
        "state_coverage_gap_2024": 1 - q(con, "SELECT SUM(paid_amt) p FROM fct_service WHERE service_year=2024").p[0] / n24.paid,
    }
    sk = q(con, """SELECT service_year, SUM(paid_amt) paid, COUNT(DISTINCT hcpcs_cd) codes FROM fct_service_national
                   WHERE regexp_matches(hcpcs_cd, '^Q4[1-3][0-9]{2}$') GROUP BY 1 ORDER BY 1""").set_index("service_year")
    k["skin_sub_paid_2023"], k["skin_sub_paid_2024"] = sk.paid[2023], sk.paid[2024]
    k["skin_sub_share_of_increase"] = (sk.paid[2024] - sk.paid[2023]) / (n24.paid - n23.paid)
    k = json.loads(json.dumps(k, default=float))
    pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path("reports/kpis.json").write_text(json.dumps(k, indent=2) + "\n")
    return k


def export_powerbi(con):
    d = pathlib.Path("powerbi"); d.mkdir(exist_ok=True)
    for t in ["dim_year", "dim_state", "dim_hcpcs", "dim_place_of_service", "fct_service", "fct_service_national", "fct_enrollment"]:
        con.execute(f"COPY (SELECT * FROM {t} ORDER BY ALL) TO '{d}/{t}.csv' (HEADER)")
    t = pathlib.Path("tableau"); t.mkdir(exist_ok=True)
    # One flat, denormalised extract (Tableau Public works best with a single wide table).
    # Grain: year x state x HCPCS for the 500 highest-paid 2024 codes; every other code is rolled up
    # into "Other codes" per service family so totals still reconcile and the file stays < 50 MB.
    con.execute("""COPY (
        WITH top AS (SELECT hcpcs_cd FROM kpi_top_hcpcs WHERE service_year = 2024 AND paid_rank <= 500)
        SELECT f.service_year, d.state_abbr, d.state_name, d.state_group, h.service_family,
               CASE WHEN t.hcpcs_cd IS NULL THEN 'OTHER' ELSE f.hcpcs_cd END AS hcpcs_cd,
               CASE WHEN t.hcpcs_cd IS NULL THEN 'Other codes (' || h.service_family || ')' ELSE h.hcpcs_desc END AS hcpcs_desc,
               p.pos_desc AS place_of_service,
               SUM(f.services) services, SUM(f.beneficiaries) beneficiaries_sum,
               ROUND(SUM(f.submitted_amt),2) submitted_amt, ROUND(SUM(f.allowed_amt),2) allowed_amt,
               ROUND(SUM(f.paid_amt),2) paid_amt, ROUND(SUM(f.standardized_amt),2) standardized_amt,
               MAX(e.ffs_part_b_benes) AS state_ffs_part_b_benes
        FROM fct_service f JOIN dim_state d USING (state_fips) JOIN dim_hcpcs h USING (hcpcs_cd)
        JOIN dim_place_of_service p USING (pos_cd)
        LEFT JOIN top t ON t.hcpcs_cd = f.hcpcs_cd
        LEFT JOIN fct_enrollment e ON e.state_fips = f.state_fips AND e.service_year = f.service_year
        GROUP BY 1,2,3,4,5,6,7,8
        ORDER BY ALL) TO 'tableau/claims_extract.csv' (HEADER)""")
    con.execute("COPY (SELECT * FROM kpi_outliers ORDER BY robust_z DESC) TO 'tableau/state_outliers.csv' (HEADER)")
