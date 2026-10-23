# Power BI model

Import every CSV in this folder (Get Data → Text/CSV). Set relationships (single direction, many-to-one):

| From (many) | To (one) | Key |
|---|---|---|
| fct_service | dim_state | state_fips |
| fct_service | dim_hcpcs | hcpcs_cd |
| fct_service | dim_place_of_service | pos_cd |
| fct_service | dim_year | service_year |
| fct_service_national | dim_hcpcs / dim_place_of_service / dim_year | as above |
| fct_enrollment | dim_state / dim_year | state_fips / service_year |

Mark `state_fips` and `hcpcs_cd` as Text (leading zeros). Paste measures from `measures.dax`.
Suggested pages: Overview (cards + family bars), Cost drivers (top-N with HCPCS Paid Rank), State variation (filled map on dim_state[state_name], Paid per FFS Part B Bene), Outliers (state_outliers.csv).
`fct_service` holds every state × HCPCS × place-of-service row for 2023-2024 (~510k rows, full detail, not a sample).
No .pbix is committed: it was built and checked in DuckDB/Python, and the dashboard PNG is a Python render in a Power BI style, not a Power BI screenshot.
