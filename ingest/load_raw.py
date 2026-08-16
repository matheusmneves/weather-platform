"""
Load downloaded NOAA files into DuckDB raw schema
- Fixed-width metadata files are parsed with a generic, schema-driven parser
- Observation csv.gz files are read directly by DuckDB via glob
- Everything lands as varchar, typing happens in dbt staging
"""

import sys
from pathlib import Path
import duckdb
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def parse_fixed_width(file_path: Path, schema: dict) -> pd.DataFrame:
    colspecs, names = [], []
    for col_name, spec in schema["columns"].items():
        colspecs.append((spec["start"] - 1, spec["end"]))  # readme is 1-indexed inclusive
        names.append(col_name)
    return pd.read_fwf(file_path, colspecs=colspecs, names=names, dtype="string")


def csv_columns_sql(schema: dict) -> str:
    columns = ", ".join(f"'{col_name}': 'VARCHAR'" for col_name in schema["columns"])
    return f"{{{columns}}}"


def main() -> int:
    cfg = load_yaml(BASE_DIR / "config" / "config.yaml")
    schemas = load_yaml(BASE_DIR / cfg["paths"]["schemas"])
    raw_dir = BASE_DIR / cfg["paths"]["raw_dir"]

    db_path = BASE_DIR / cfg["paths"]["duckdb_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for table_name, schema in schemas.items():
        if schema.get("format") == "csv":
            continue

        file_path = raw_dir / "metadata" / schema["filename"]
        df = parse_fixed_width(file_path, schema)
        con.register("df_view", df)
        con.execute(f"CREATE OR REPLACE TABLE raw.{table_name} AS SELECT * FROM df_view")
        con.unregister("df_view")
        print(f"[loaded] raw.{table_name}: {len(df):,} rows")

    observations_schema = schemas["observations"]
    obs_glob = str(raw_dir / "observations" / observations_schema["filename"])
    con.execute(f"""
        CREATE OR REPLACE TABLE raw.observations AS
        SELECT * FROM read_csv(
            '{obs_glob}',
            header = false,
            columns = {csv_columns_sql(observations_schema)}
        )
    """)
    n = con.execute("SELECT COUNT(*) FROM raw.observations").fetchone()[0]
    print(f"[loaded] raw.observations: {n:,} rows")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
