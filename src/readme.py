"""Render README.md from docs/README.template.md + reports/kpis.json + data/manifest.json (no hand-typed numbers)."""
import json, pathlib, duckdb


def main():
    k = json.loads(pathlib.Path("reports/kpis.json").read_text())
    m = json.loads(pathlib.Path("data/manifest.json").read_text())
    con = duckdb.connect("data/claims.duckdb", read_only=True)
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
              ["stg_phys", "stg_enrollment", "dim_state", "dim_hcpcs", "fct_service", "fct_service_national", "fct_enrollment"]}
    con.close()
    g0 = k["top_growth"][0]; g1 = k["top_growth"][1]; o = k["top_outlier"]
    f = {
        "paid": f"${k['paid_2024']/1e9:,.1f}B", "paid23": f"${k['paid_2023']/1e9:,.1f}B", "paid_yoy": f"{k['paid_yoy']:+.1%}",
        "svc": f"{k['services_2024']/1e9:,.2f}B", "svc_yoy": f"{k['services_yoy']:+.1%}",
        "ppb": f"${k['paid_per_ffs_b_bene_2024']:,.0f}", "ppb23": f"${k['paid_per_ffs_b_bene_2023']:,.0f}",
        "ppb_yoy": f"{k['paid_per_ffs_b_bene_2024']/k['paid_per_ffs_b_bene_2023']-1:+.1%}",
        "benes": f"{k['ffs_part_b_benes_2024']/1e6:,.1f}M",
        "pps": f"${k['paid_per_service_2024']:,.2f}", "p2a": f"{k['paid_to_allowed_2024']:.1%}", "c2a": f"{k['charge_to_allowed_2024']:.2f}",
        "codes80": f"{k['codes_for_80pct_paid']:,}", "codes": f"{k['hcpcs_codes_2024']:,}", "top10": f"{k['top10_share']:.1%}",
        "topcode": k["top_code"]["code"], "topshare": f"{k['top_code']['share']:.1%}", "toppaid": f"${k['top_code']['paid']/1e9:,.2f}B",
        "drug": f"{k['drug_share']:.1%}", "drugpaid": f"${k['drug_paid']/1e9:,.1f}B",
        "g0": f"{g0['hcpcs_cd']} ({g0['hcpcs_desc']})", "g0prior": f"${g0['paid']/(1+g0['paid_yoy'])/1e6:,.1f}M", "g0paid": f"${g0['paid']/1e6:,.0f}M",
        "g1": f"{g1['hcpcs_cd']} ({g1['hcpcs_desc']})", "g1prior": f"${g1['paid']/(1+g1['paid_yoy'])/1e6:,.0f}M", "g1paid": f"${g1['paid']/1e6:,.0f}M",
        "shi": k["state_high"]["name"], "shiv": f"${k['state_high']['value']:,.0f}", "slo": k["state_low"]["name"], "slov": f"${k['state_low']['value']:,.0f}",
        "sratio": f"{k['state_ratio']:.1f}", "stdratio": f"{k['std_ratio']:.1f}",
        "ocells": k["outlier_cells"], "ocodes": k["outlier_codes"],
        "ost": o["state_abbr"], "ocd": o["hcpcs_cd"], "odesc": o["hcpcs_desc"], "oratio": f"{o['ratio_to_median']:.1f}",
        "skin23": f"{k['skin_sub_paid_2023']/1e9:,.2f}", "skin24": f"{k['skin_sub_paid_2024']/1e9:,.2f}",
        "skinshare": f"{k['skin_sub_share_of_increase']:.0%}",
        "gap": f"{k['state_coverage_gap_2024']:.1%}",
        "sources": "\n".join(f"| {s['dataset']} | [landing]({s['landing']}) · [file]({s['url']}) | {s['bytes']:,} | `{s['sha256'][:16]}…` |" for s in m["files"]),
        "licence": m["licence"], "publisher": m["publisher"],
        **{f"n_{t}": f"{n:,}" for t, n in counts.items()},
    }
    tpl = pathlib.Path("docs/README.template.md").read_text()
    pathlib.Path("README.md").write_text(tpl.format(**f))


if __name__ == "__main__":
    main()
