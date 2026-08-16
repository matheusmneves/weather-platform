"""
Download NOAA GHCN daily observation and metadata files
Idempotent: files already present in data/raw are skipped
Station list is read from dbt seed (single source of config)
"""

import csv
import sys
from pathlib import Path
import requests
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]

def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml") as f:
        return yaml.safe_load(f)

def read_target_stations(seed_path: Path) -> list[str]:
    with open(seed_path, newline="") as f:
        return [row["station_id"] for row in csv.DictReader(f)]

def download_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"[skip] {dest.name} already exists")
        return
    print(f"[download] {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=180)
    resp.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    tmp.rename(dest)
    print(f"[ok] {dest.name}")

def main() -> init:
    cfg = load_config()
    base_url = cfg["noaa"]["base_url"]
    raw_dir = BASE_DIR / cfg["paths"]["raw_dir"]

    for fname in cfg["noaa"]["metadata_files"]:
        download_file(f"{base_url}/{fname}", raw_dir / "metadata" / fname)

    for station_id in read_target_stations(BASE_DIR / cfg["paths"]["stations_seed"]):
        fname = f"{station_id}.csv.gz"
        download_file(f"{base_url}/by_station/{fname}", raw_dir / "observations" / fname)

    return 0


if __name__ == "__main__":
    sys.exit(main())