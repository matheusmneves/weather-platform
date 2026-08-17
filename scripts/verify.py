"""Sanity check: narrative/mart parity and per-city coverage."""
import duckdb

con = duckdb.connect("data/weather.duckdb", read_only=True)

tables = {r[0] for r in con.execute(
    "select table_name from information_schema.tables where table_schema = 'main'"
).fetchall()}

mart_rows = con.execute("select count(*) from main.mart_daily_weather").fetchone()[0]

if "narratives" in tables:
    n = con.execute("select count(*) from main.narratives").fetchone()[0]
    parity = "OK" if n == mart_rows else "MISMATCH"
    print(f"narratives: {n} | mart_rows: {mart_rows} | parity: {parity}")
else:
    print(f"mart_rows: {mart_rows} | narratives: not generated yet (run `make narratives`)")

print(con.execute(
    "select city, count(*) as days, min(obs_date) as first_day, max(obs_date) as last_day "
    "from main.mart_daily_weather group by city order by city"
).df())