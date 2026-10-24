# Medicare Claims KPI Dashboard: cost drivers, state variation and outliers

**DuckDB SQL star schema, pytest data checks, and Power BI / Tableau-ready exports built on {n_stg_phys} rows of real CMS Medicare Part B claims aggregates (2023-2024).**
The KPIs are the ones a health-insurer BI team reports: paid amount, cost per member, cost drivers, regional variation and utilisation outliers.

![dashboard](reports/dashboard.png)

Exports: [PNG](reports/dashboard.png) · [PDF](reports/dashboard.pdf) · [self-contained HTML](reports/dashboard.html) · [kpis.json](reports/kpis.json)

## Problem and business questions
A medical-claims analytics team at a payer (for example a KSA insurer reporting to CHI) needs a repeatable KPI layer to answer:
1. How much did we pay, for how many services, and how fast is it growing?
2. What is the cost per covered member, and how is it trending?
3. Which services drive cost, and how concentrated is spend?
4. Which regions cost more per member, and is that price or utilisation?
5. Which region × service combinations are statistical outliers worth a utilisation review?
6. Approval/denial rates: **not answerable with this data.** CMS publishes only paid (adjudicated) claims, so no denial KPI was invented.

## Headline findings (2024 service year, generated from `reports/kpis.json`)
| # | Finding | So what |
|---|---|---|
| 1 | Medicare paid **{paid}** for {svc} physician/practitioner services, **{paid_yoy}** on 2023 ({paid23}); services grew {svc_yoy}. | Spend grew faster than volume, so mix and intensity (not only volume) are driving cost. |
| 2 | Paid per FFS Part B beneficiary was **{ppb}** ({ppb_yoy} vs {ppb23}) across {benes} beneficiaries. | This is a PMPY-style cost-per-member figure, the core trend KPI for pricing and reserving. |
| 3 | **{codes80}** of {codes} billed codes made up 80% of paid. The top 10 codes are {top10}, and {topcode} (established office visit) alone is {topshare} ({toppaid}). | Cost-containment work can focus on a few hundred codes. |
| 4 | Part B drugs were **{drug}** of paid ({drugpaid}). Skin-substitute codes (Q4100-Q4399) rose from ${skin23}B to **${skin24}B**, about {skinshare} of the whole year-on-year increase. {g0} alone went from {g0prior} to {g0paid}. | One fast-growing product category can dominate the growth. This is a classic payment-integrity watch-list item. |
| 5 | Paid per beneficiary by provider state ranges **{sratio}×**, from {shi} ({shiv}) to {slo} ({slov}). After CMS price standardisation the spread is still {stdratio}×. | Regional variation is mostly utilisation and patient flow, not local price levels, so network and utilisation management matter more than tariffs. |
| 6 | **{ocells}** state × code cells across {ocodes} of the top-100 codes are robust-z outliers (abs(z) > 3.5). The largest is {ost} {ocd} ({odesc}) at **{oratio}×** the median state rate. | These are review candidates, not findings of wrongdoing. Billing patterns such as mass immunisers registered in one state could explain some of them. That is not tested here. |

All findings are descriptive and correlational.

## Data and licence
Publisher: {publisher}. Licence: {licence}.

| Dataset | Links | Bytes | SHA-256 |
|---|---|---|---|
{sources}

Full checksums and download times (UTC) are in [`data/manifest.json`](data/manifest.json). Raw files are downloaded by script and kept out of git.

**What this data is:** real CMS aggregates of Medicare fee-for-service Part B physician/practitioner claims, one row per geography × HCPCS code × place of service. It is not synthetic and it is not member-level.

## Data issues found while profiling
- **Suppression:** CMS drops state cells with fewer than 11 beneficiaries, so state rows total {gap} less paid than the national rows. National KPIs therefore use the national rows (tested).
- **Blank geography:** 5 state-level rows per release have no state code or name. They are kept as `ZZ / Unspecified` and pinned in a test.
- **No claim or denial counts:** `Tot_Srvcs` counts service line units (drug codes count billing units such as per-mg), not claims. "Services" is not "claims".
- **Beneficiaries are not additive** across codes. Cost per member therefore uses the CMS Medicare Monthly Enrollment FFS Part B count as denominator. The enrollment file uses `*` for suppressed cells (parsed as NULL).
- **Geography mismatch:** claims are by rendering-provider state, enrollment by beneficiary residence. States with snowbirds or cross-border referral centres (e.g. FL, DC) can look high.
- Non-state geographies (territories, armed forces, foreign, unknown) are kept in the model but excluded from state rankings.

## Approach
```
CMS CSVs (3) ──► sql/01_staging.sql  typed, renamed, unioned 2023+2024
             ──► sql/02_star.sql     dim_year, dim_state, dim_hcpcs (+service family), dim_place_of_service
                                     fct_service (state grain), fct_service_national, fct_enrollment
             ──► sql/03_kpis.sql     kpi_national_year, kpi_family_year, kpi_top_hcpcs (RANK, running share, YoY),
                                     kpi_state_year, kpi_outliers (median/MAD robust z), kpi_pos_year
             ──► reports/kpis.json ─► dashboard (PNG/PDF/HTML) + README (this file is generated)
             ──► powerbi/*.csv + measures.dax     tableau/claims_extract.csv + BUILD_NOTES.md
```

| Table | Rows |
|---|---|
| stg_phys | {n_stg_phys} |
| stg_enrollment | {n_stg_enrollment} |
| dim_state / dim_hcpcs | {n_dim_state} / {n_dim_hcpcs} |
| fct_service | {n_fct_service} |
| fct_service_national | {n_fct_service_national} |
| fct_enrollment | {n_fct_enrollment} |

## KPI definitions
| KPI | Definition |
|---|---|
| Paid | Σ (Tot_Srvcs × Avg_Mdcr_Pymt_Amt). Medicare's payment after deductible and coinsurance |
| Allowed / Submitted | same with Avg_Mdcr_Alowd_Amt / Avg_Sbmtd_Chrg. Paid/allowed = {p2a}, charges = {c2a}× allowed |
| Paid per service | Paid / services ({pps}) |
| Paid per FFS Part B beneficiary | Paid / annual Original Medicare Part B enrollees (national or state) |
| Price index | Paid / standardised amount (CMS removes geographic pricing adjustments). Above 1 means a high-price area |
| Cost concentration | number of codes whose cumulative paid reaches 80% (window function) |
| Outlier | for the top-100 codes by 2024 paid: state services per 1,000 FFS Part B beneficiaries, robust z = 0.6745·(ln x − median)/MAD across 51 jurisdictions, flagged at abs(z) > 3.5 |

## Power BI and Tableau
- `powerbi/`: star-schema CSVs (full detail, not sampled), [`measures.dax`](powerbi/measures.dax) mirroring the SQL, and relationship notes in [`powerbi/README.md`](powerbi/README.md). The dashboard image is a Power BI-style render made in Python, not a Power BI screenshot, and no .pbix is included.
- `tableau/`: a Tableau Public-ready flat extract (top-500 codes + "Other" roll-ups, reconciles to the fact table) and [build notes](tableau/BUILD_NOTES.md). **It has not been published to Tableau Public**, because that needs the author's own sign-in.

## Reference repos studied (and what was borrowed)
| Repo | Borrowed |
|---|---|
| [priyasg16/healthcare-claims-denial-analysis](https://github.com/priyasg16/healthcare-claims-denial-analysis) | Uses CMS provider data in a star schema with submitted-vs-paid variance and geographic benchmarking. Borrowed the charge-to-allowed and state benchmark KPIs. |
| [sana1410/RCM](https://github.com/sana1410/RCM) | Layered bronze/silver/gold modelling and a payer KPI list. Borrowed the staging → star → KPI layering, and dropped its denial-rate KPI because this data has no denials. |
| [vigneshwari2408/healthcare-claims-analytics-dashboard](https://github.com/vigneshwari2408/healthcare-claims-analytics-dashboard) | "The problem" framing and an overview → drill-down page plan. Borrowed the business-question-first README and page structure. |
| [CharRich926/healthcare-data-analytics-portfolio](https://github.com/CharRich926/healthcare-data-analytics-portfolio) | Explicit data-provenance disclaimer and named DAX measures (YoY, rate measures). Borrowed the DAX naming and the honesty note about what the data is and is not. |
| [dbt-labs/jaffle_shop_duckdb](https://github.com/dbt-labs/jaffle_shop_duckdb) | Layered SQL on DuckDB with tests at each layer. Borrowed the numbered SQL layers and data tests on keys and relationships. |

## Reproduce
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt      # exact pins
python run.py                        # download (~300 MB, checksum-verified) → SQL → exports → dashboard → README → pytest
```
Tested on Python 3.13. A clean-venv rebuild produced byte-identical `kpis.json`.

## Tests
`tests/test_data_quality.py` checks: manifest checksums, row counts pinned to the CMS files, unique grain, foreign keys, paid ≤ allowed, the CMS <11 suppression rule, state ≤ national totals, the documented blank-state anomaly, enrollment coverage, family shares summing to 1, recomputed KPIs, a Tableau extract that reconciles, GitHub-safe file sizes, and README numbers matching `kpis.json`.

## Limitations
- Medicare FFS Part B (US, mostly aged 65+) is a proxy. Utilisation and price levels differ greatly from KSA private/CCHI-regulated insurance, so the method transfers, not the numbers.
- The data is aggregated (no member, claim or provider IDs). Outlier detection is at state × code level, not provider level.
- There are no approval, denial, rejection or turnaround fields, so those KPIs are deliberately absent.
- Only two annual points, so growth figures are YoY in nominal USD with no inflation adjustment and no seasonality.
- Service units for drug codes are billing units, so "paid per service" mixes units across code types.

## Author
Amir Khan · [github.com/amirator](https://github.com/amirator). This is a personal portfolio project, not affiliated with CMS or any insurer.
