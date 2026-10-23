"""Data-quality and reproducibility checks (run after `python run.py`)."""
import json, pathlib, re
import duckdb, pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(ROOT / "data/claims.duckdb"), read_only=True); yield c; c.close()


def one(con, sql): return con.execute(sql).fetchone()[0]


def test_manifest_checksums_match_raw_files():
    import hashlib
    m = json.loads((ROOT / "data/manifest.json").read_text())
    assert len(m["files"]) == 3
    for f in m["files"]:
        h = hashlib.sha256((ROOT / "data/raw" / f["file"]).read_bytes()).hexdigest()
        assert h == f["sha256"], f["file"]


def test_row_counts_pinned_to_source(con):
    # pinned to the published CMS files (rows excluding header)
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE service_year=2023") == 268_634
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE service_year=2024") == 268_350


def test_grain_is_unique(con):
    assert one(con, """SELECT COUNT(*) FROM (SELECT service_year,state_fips,hcpcs_cd,pos_cd FROM fct_service
                       GROUP BY ALL HAVING COUNT(*)>1)""") == 0
    assert one(con, """SELECT COUNT(*) FROM (SELECT service_year,hcpcs_cd,pos_cd FROM fct_service_national
                       GROUP BY ALL HAVING COUNT(*)>1)""") == 0
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT hcpcs_cd) FROM dim_hcpcs") == 0


def test_foreign_keys_resolve(con):
    for fk, dim in [("state_fips", "dim_state"), ("hcpcs_cd", "dim_hcpcs"), ("pos_cd", "dim_place_of_service"), ("service_year", "dim_year")]:
        assert one(con, f"SELECT COUNT(*) FROM fct_service f ANTI JOIN {dim} d USING ({fk})") == 0, fk


def test_amounts_non_negative_and_ordered(con):
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE services<=0 OR beneficiaries<=0 OR avg_paid<0") == 0
    # Medicare pays at most what it allows (cent-level rounding tolerance)
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE avg_paid > avg_allowed + 0.01") == 0


def test_cms_suppression_rule(con):
    # CMS suppresses cells with fewer than 11 beneficiaries
    assert one(con, "SELECT MIN(beneficiaries) FROM stg_phys") >= 11


def test_states_sum_to_less_than_national(con):
    gap = one(con, """SELECT 1 - (SELECT SUM(paid_amt) FROM fct_service WHERE service_year=2024)
                             / (SELECT SUM(paid_amt) FROM fct_service_national WHERE service_year=2024)""")
    assert 0 < gap < 0.03   # state rows lose suppressed small cells, never more than the national total


def test_documented_source_anomaly_blank_state(con):
    # 5 state-level rows per release have a blank geography code and name: kept as 'ZZ' and documented
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE state_fips='ZZ' AND service_year=2024") == 5
    assert one(con, "SELECT COUNT(*) FROM stg_phys WHERE state_fips='ZZ' AND service_year=2023") == 5


def test_enrollment_covers_all_51_jurisdictions(con):
    assert one(con, """SELECT COUNT(*) FROM fct_enrollment JOIN dim_state USING (state_fips)
                       WHERE state_group='50 states + DC' AND ffs_part_b_benes > 0""") == 102


def test_family_shares_sum_to_one(con):
    for y in (2023, 2024):
        assert abs(one(con, f"SELECT SUM(share_of_paid) FROM kpi_family_year WHERE service_year={y}") - 1) < 1e-9


def test_kpis_recompute(con):
    k = json.loads((ROOT / "reports/kpis.json").read_text())
    paid = one(con, "SELECT SUM(paid_amt) FROM fct_service_national WHERE service_year=2024")
    assert abs(paid - k["paid_2024"]) < 1
    benes = one(con, "SELECT ffs_part_b_benes FROM stg_enrollment WHERE state_abbr='US' AND enrol_year=2024")
    assert abs(paid / benes - k["paid_per_ffs_b_bene_2024"]) < 0.01


def test_outputs_exist_and_sizes_github_safe():
    for p in ["reports/dashboard.png", "reports/dashboard.pdf", "reports/dashboard.html", "powerbi/measures.dax",
              "powerbi/fct_service.csv", "tableau/claims_extract.csv", "tableau/BUILD_NOTES.md"]:
        f = ROOT / p
        assert f.exists() and f.stat().st_size > 0, p
        assert f.stat().st_size < 50 * 1024 * 1024, p   # GitHub warns above 50 MB


def test_tableau_extract_reconciles(con):
    t = one(con, "SELECT SUM(paid_amt) FROM read_csv('" + str(ROOT / "tableau/claims_extract.csv") + "')")
    f = one(con, "SELECT SUM(paid_amt) FROM fct_service")
    assert abs(t - f) / f < 1e-6


def test_readme_numbers_match_kpis():
    k = json.loads((ROOT / "reports/kpis.json").read_text())
    r = (ROOT / "README.md").read_text()
    for s in [f"${k['paid_2024']/1e9:,.1f}B", f"${k['paid_per_ffs_b_bene_2024']:,.0f}", f"{k['codes_for_80pct_paid']:,}",
              f"{k['state_ratio']:.1f}×", f"{k['drug_share']:.1%}"]:
        assert s in r, s
    assert not re.search(r"\{[a-z_0-9]+\}", r), "unfilled template field"
