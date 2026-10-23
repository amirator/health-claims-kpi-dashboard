# Tableau Public build notes

**Not published.** Tableau Public needs an interactive sign-in by the author, so this repo ships a
Tableau Public-ready extract plus these notes. Nothing has been uploaded to public.tableau.com.

Files
- `claims_extract.csv`: one wide table, grain = year × provider state × HCPCS × place of service for the 500 highest-paid
  2024 codes. All other codes are rolled up into `OTHER` / "Other codes (<family>)" rows, so state totals still reconcile with `fct_service`.
  Includes `state_ffs_part_b_benes` (repeated per row; aggregate with MAX or a FIXED LOD, never SUM).
- `state_outliers.csv`: top-100 codes × 51 jurisdictions with services per 1k beneficiaries, robust z and an outlier flag.

Steps (Tableau Public desktop app, free)
1. Connect → Text file → `claims_extract.csv`. Set `hcpcs_cd` to String and `state_abbr` geographic role = State/Province.
2. Calculated fields:
   - `Benes (state)` = `{ FIXED [service_year],[state_abbr] : MAX([state_ffs_part_b_benes]) }`
   - `Paid per bene` = `SUM([paid_amt]) / SUM({ FIXED [service_year],[state_abbr] : MAX([state_ffs_part_b_benes]) })` (use at state level)
   - `Paid YoY` = table calc: `(ZN(SUM([paid_amt])) - LOOKUP(ZN(SUM([paid_amt])), -1)) / ABS(LOOKUP(ZN(SUM([paid_amt])), -1))` along service_year
   - `Price index` = `SUM([paid_amt]) / SUM([standardized_amt])`
3. Sheets: KPI BANs; filled map of Paid per bene (filter state_group = "50 states + DC", year = 2024); bar of top-10 HCPCS by paid
   (exclude OTHER); family bars by year; scatter from `state_outliers.csv` (log axes, colour by is_outlier).
4. Dashboard 1600×1000, source caption: "CMS Medicare Physician & Other Practitioners by Geography and Service, 2023-2024. Public domain."
5. File → Save to Tableau Public (this needs the author's own account).
