"""Download the CMS public-use files (skips files whose SHA-256 already matches the manifest)."""
import hashlib, json, pathlib, urllib.request, datetime

RAW = pathlib.Path("data/raw"); MANIFEST = pathlib.Path("data/manifest.json")
LANDING_PHYS = ("https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/"
                "medicare-physician-other-practitioners-by-geography-and-service")
SOURCES = [
    {"file": "MUP_PHY_R25_P05_V20_D23_Geo.csv", "dataset": "Medicare Physician & Other Practitioners - by Geography and Service (2023 service year)",
     "url": "https://data.cms.gov/sites/default/files/2025-04/3b718a11-a28d-4c38-a13b-2c6eeb649980/MUP_PHY_R25_P05_V20_D23_Geo.csv",
     "landing": LANDING_PHYS},
    {"file": "MUP_PHY_R26_P05_V10_D24_Geo.csv", "dataset": "Medicare Physician & Other Practitioners - by Geography and Service (2024 service year)",
     "url": "https://data.cms.gov/sites/default/files/2026-05/e534c74b-79b8-4892-8a95-5a17e2dfec9f/MUP_PHY_R26_P05_V10_D24_Geo.csv",
     "landing": LANDING_PHYS},
    {"file": "enrollment.csv", "dataset": "Medicare Monthly Enrollment (July 2026 release; annual state rows used)",
     "url": "https://data.cms.gov/sites/default/files/2026-10/c41a8ac2-8229-4f3b-a4cb-423d9cd5328a/Medicare%20Monthly%20Enrollment%20Data_July%202026.csv",
     "landing": "https://data.cms.gov/summary-statistics-on-beneficiary-enrollment/medicare-and-medicaid-reports/medicare-monthly-enrollment"},
]
PUBLISHER = "Centers for Medicare & Medicaid Services (CMS), Office of Enterprise Data and Analytics"
LICENCE = "U.S. federal government work, public domain (data.cms.gov accessLevel=public; no copyright restrictions)"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    old = {e["file"]: e for e in json.loads(MANIFEST.read_text())["files"]} if MANIFEST.exists() else {}
    out = []
    for s in SOURCES:
        p = RAW / s["file"]
        if not (p.exists() and s["file"] in old and sha256(p) == old[s["file"]]["sha256"]):
            print("downloading", s["url"])
            urllib.request.urlretrieve(s["url"], p)
            ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            ts = old[s["file"]]["downloaded_utc"]
        out.append({**s, "bytes": p.stat().st_size, "sha256": sha256(p), "downloaded_utc": ts})
    MANIFEST.write_text(json.dumps({"publisher": PUBLISHER, "licence": LICENCE, "files": out}, indent=2) + "\n")


if __name__ == "__main__":
    main()
