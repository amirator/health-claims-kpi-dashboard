"""Power BI-style one-page dashboard -> reports/dashboard.png, .pdf and self-contained .html"""
import base64, io, json, pathlib, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

NAVY, TEAL, GREY, RED, LIGHT = "#1F3A5F", "#0E9F9A", "#8A94A6", "#D64545", "#F3F5F8"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 10.5,
                     "axes.titlelocation": "left"})


def bn(x): return f"${x/1e9:,.1f}B"
def short(s, n=34): return s if len(s) <= n else s[:n - 1] + "…"


def card(fig, x, y, w, h, title, value, sub):
    ax = fig.add_axes([x, y, w, h]); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06",
                                fc="white", ec="#D9DEE7", transform=ax.transAxes))
    ax.add_patch(plt.Rectangle((0, 0), 0.025, 1, color=TEAL, transform=ax.transAxes))
    ax.text(0.08, 0.76, title, color=GREY, fontsize=9, transform=ax.transAxes)
    ax.text(0.08, 0.36, value, color=NAVY, fontsize=19, weight="bold", transform=ax.transAxes)
    ax.text(0.08, 0.1, sub, color=GREY, fontsize=8, transform=ax.transAxes)


def main(con):
    k = json.loads(pathlib.Path("reports/kpis.json").read_text())
    fam = con.sql("SELECT * FROM kpi_family_year").df()
    top = con.sql("SELECT * FROM kpi_top_hcpcs WHERE service_year=2024 AND paid_rank<=10 ORDER BY paid_rank").df()
    st = con.sql("SELECT * FROM kpi_state_year WHERE service_year=2024 ORDER BY paid_per_ffs_b_bene").df()
    out = con.sql("SELECT * FROM kpi_outliers").df()
    grow = con.sql("""SELECT * FROM kpi_top_hcpcs WHERE service_year=2024 AND paid_rank<=50 AND paid_yoy IS NOT NULL
                      ORDER BY paid*paid_yoy/(1+paid_yoy) DESC LIMIT 8""").df()

    fig = plt.figure(figsize=(17, 11), facecolor=LIGHT)
    hdr = fig.add_axes([0, 0.935, 1, 0.065]); hdr.axis("off")
    hdr.add_patch(plt.Rectangle((0, 0), 1, 1, color=NAVY, transform=hdr.transAxes))
    hdr.text(0.015, 0.55, "Medicare Part B Physician & Practitioner Claims — KPI Dashboard", color="white",
             fontsize=17, weight="bold", va="center", transform=hdr.transAxes)
    hdr.text(0.015, 0.18, "Service years 2023–2024 · Fee-for-service · CMS public-use files · all amounts nominal USD",
             color="#C9D6E8", fontsize=9.5, va="center", transform=hdr.transAxes)

    cards = [("Medicare paid 2024", bn(k["paid_2024"]), f"{k['paid_yoy']:+.1%} vs 2023"),
             ("Services (line items) 2024", f"{k['services_2024']/1e9:,.2f}B", f"{k['services_yoy']:+.1%} vs 2023"),
             ("Paid per FFS Part B beneficiary", f"${k['paid_per_ffs_b_bene_2024']:,.0f}",
              f"2023: ${k['paid_per_ffs_b_bene_2023']:,.0f}"),
             ("Paid per service", f"${k['paid_per_service_2024']:,.2f}", f"paid / allowed = {k['paid_to_allowed_2024']:.1%}"),
             ("Codes making up 80% of paid", f"{k['codes_for_80pct_paid']:,}", f"of {k['hcpcs_codes_2024']:,} billed HCPCS codes")]
    for i, c in enumerate(cards):
        card(fig, 0.015 + i * 0.197, 0.83, 0.185, 0.09, *c)

    # Wide panel: paid by service family, 2023 vs 2024
    ax = fig.add_axes([0.145, 0.53, 0.47, 0.25])
    p = fam.pivot(index="service_family", columns="service_year", values="paid").sort_values(2024)
    y = range(len(p))
    ax.barh([i + 0.2 for i in y], p[2023] / 1e9, height=0.4, color=GREY, label="2023")
    ax.barh([i - 0.2 for i in y], p[2024] / 1e9, height=0.4, color=NAVY, label="2024")
    ax.set_yticks(list(y), p.index)
    for i, (a, b) in enumerate(zip(p[2023], p[2024])):
        ax.text(b / 1e9 + 0.3, i - 0.2, f"${b/1e9:,.1f}B ({b/a-1:+.0%})", va="center", fontsize=8, color=NAVY)
    ax.set_xlabel("Medicare paid, $ billions"); ax.legend(frameon=False, loc="lower right")
    ax.set_title("Where the money goes: paid by service family, 2023 vs 2024")
    ax.set_xlim(0, p.values.max() / 1e9 * 1.25)

    # Top 10 cost drivers
    ax = fig.add_axes([0.73, 0.53, 0.25, 0.25])
    t = top.iloc[::-1]
    ax.barh([f"{c}  {short(d, 26)}" for c, d in zip(t.hcpcs_cd, t.hcpcs_desc)], t.paid / 1e9, color=TEAL)
    for i, (v, s) in enumerate(zip(t.paid, t.share_of_paid)):
        ax.text(v / 1e9 + 0.1, i, f"{s:.1%}", va="center", fontsize=8)
    ax.set_title("Top 10 cost drivers, 2024 (share of paid)"); ax.set_xlabel("$ billions")
    ax.tick_params(axis="y", labelsize=7.5); ax.set_xlim(0, t.paid.max() / 1e9 * 1.2)

    # State variation
    ax = fig.add_axes([0.05, 0.1, 0.36, 0.35])
    colors = [RED if i >= len(st) - 5 else (TEAL if i < 5 else "#9FB3CC") for i in range(len(st))]
    ax.bar(st.state_abbr, st.paid_per_ffs_b_bene, color=colors)
    ax.plot(st.state_abbr, st.std_per_ffs_b_bene, "o", ms=2.5, color=NAVY, label="price-standardised")
    ax.axhline(k["paid_per_ffs_b_bene_2024"], color=NAVY, lw=1, ls="--")
    ax.text(0, k["paid_per_ffs_b_bene_2024"] + 90, "national", fontsize=7.5, color=NAVY)
    ax.tick_params(axis="x", rotation=90, labelsize=6.5); ax.legend(frameon=False, loc="upper left", fontsize=8)
    ax.set_title(f"Paid per FFS Part B beneficiary by provider state, 2024 ({k['state_ratio']:.1f}× spread)")
    ax.set_ylabel("$ per beneficiary")

    # Fastest-growing large codes
    ax = fig.add_axes([0.52, 0.1, 0.17, 0.35])
    g = grow.iloc[::-1]; prior = g.paid / (1 + g.paid_yoy)
    ax.barh([f"{c} {short(d, 18)}" for c, d in zip(g.hcpcs_cd, g.hcpcs_desc)], (g.paid - prior) / 1e6, color=RED)
    ax.set_title("Biggest $ increases, 2023→24"); ax.set_xlabel("added paid, $ millions")
    ax.tick_params(axis="y", labelsize=7.5)

    # Outliers
    ax = fig.add_axes([0.75, 0.1, 0.23, 0.35])
    n = out[~out.is_outlier.fillna(False)]; o = out[out.is_outlier.fillna(False)]
    ax.scatter(n.median_svc_per_1k, n.svc_per_1k, s=5, color="#B8C4D6", label="within range")
    ax.scatter(o.median_svc_per_1k, o.svc_per_1k, s=14, color=RED, label=f"outlier |z|>3.5 (n={len(o)})")
    ax.set_xscale("log"); ax.set_yscale("log")
    lim = [out[["median_svc_per_1k", "svc_per_1k"]].min().min() * 0.8, out[["median_svc_per_1k", "svc_per_1k"]].max().max() * 1.2]
    ax.plot(lim, lim, color=GREY, lw=0.8)
    for j, (_, r) in enumerate(o.nlargest(2, "robust_z").iterrows()):
        ax.annotate(f"{r.state_abbr} {r.hcpcs_cd} ({r.ratio_to_median:.0f}× median)", (r.median_svc_per_1k, r.svc_per_1k), fontsize=7, xytext=(-150, 4 - 22 * j), textcoords="offset points", arrowprops=dict(arrowstyle="-", color=GREY, lw=0.6))
    ax.set_xlabel("national median state rate (services / 1k benes)"); ax.set_ylabel("state rate")
    ax.set_title("Utilisation outliers: top-100 codes × 51 states"); ax.legend(frameon=False, fontsize=7.5, loc="upper left")

    fig.text(0.015, 0.012, "Source: CMS Medicare Physician & Other Practitioners – by Geography and Service (2023, 2024); CMS Medicare Monthly "
             "Enrollment (annual FFS Part B beneficiaries). Public domain. No denial/approval data exists in these files.\n"
             "State = rendering-provider state; denominators = beneficiary residence. Built by Amir Khan (github.com/amirator).",
             fontsize=7.8, color=GREY)

    rp = pathlib.Path("reports")
    fig.savefig(rp / "dashboard.png", dpi=110, facecolor=LIGHT)
    fig.savefig(rp / "dashboard.pdf", facecolor=LIGHT)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110, facecolor=LIGHT); plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()
    tbl = top[["paid_rank", "hcpcs_cd", "hcpcs_desc", "service_family", "paid", "share_of_paid", "paid_yoy"]].copy()
    tbl["paid"] = tbl.paid.map(bn); tbl["share_of_paid"] = tbl.share_of_paid.map("{:.1%}".format)
    tbl["paid_yoy"] = tbl.paid_yoy.map(lambda v: f"{v:+.1%}")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Medicare claims KPI dashboard</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;background:{LIGHT};margin:20px;color:#222}}img{{max-width:100%}}
table{{border-collapse:collapse;background:white}}td,th{{border:1px solid #ddd;padding:4px 8px;font-size:13px}}th{{background:{NAVY};color:white}}</style>
</head><body><img alt="dashboard" src="data:image/png;base64,{b64}"><h3>Top 10 cost drivers, 2024</h3>{tbl.to_html(index=False)}
<p style="color:{GREY};font-size:12px">Self-contained export; numbers from reports/kpis.json.</p></body></html>"""
    (rp / "dashboard.html").write_text(html)
