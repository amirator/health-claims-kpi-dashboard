"""One command: python run.py  (download -> DuckDB SQL -> KPIs + Power BI/Tableau exports -> dashboard -> README -> tests)"""
import subprocess, sys
from src import download, build, dashboard, readme
download.main()
con = build.build(); build.export_kpis(con); build.export_powerbi(con)
dashboard.main(con); con.close(); readme.main()
sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q"]))
