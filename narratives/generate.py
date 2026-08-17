"""Bulk daily weather narrative generation via Gemini.

Design:
- State lives in the database: the `narratives` table with a composite PK
  (station_id, obs_date) is the idempotency contract.
- Pending work is DERIVED (anti-join mart vs narratives), never tracked in files.
  Re-running after any failure resumes exactly where it stopped.
- Batched calls with structured JSON output; each item must echo its keys.
  Items with missing/hallucinated keys are discarded and naturally reappear
  as pending on the next pass.
- Element semantics in the prompt:
    * element never reported by the station (per inventory) -> key omitted entirely
    * value NULL (QA gap)                                    -> explicitly "no data"
    * value present (including zero)                          -> stated as fact
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
import yaml
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

META_KEYS = {"city", "station_id", "station_name", "obs_date",
             "latitude", "longitude", "elevation_m"}

DDL = """
create table if not exists main.narratives (
    station_id   varchar not null,
    obs_date     date    not null,
    narrative    varchar not null,
    model_name   varchar,
    generated_at timestamp default current_timestamp,
    primary key (station_id, obs_date)
)
"""

PENDING_SQL = """
select m.*
from main.mart_daily_weather as m
left join main.narratives as n
  on  m.station_id = n.station_id
  and m.obs_date   = n.obs_date
where n.station_id is null
order by m.station_id, m.obs_date
limit ?
"""

EXPECTED_SQL = """
select station_id, lower(element) as element
from main.int_station_elements
"""

UNITS_SQL = """
select lower(element) as element, unit
from main.element_config
"""

PROMPT_TEMPLATE = """You are a concise weather reporter. For EACH record below, write a short
(2-3 sentence) daily weather narrative for that station and date.

Rules:
- Each record is fully independent. NEVER reference other records, other days, or other cities.
- Use ONLY the data provided. Never invent or estimate values.
- Always state values WITH their units, per the legend below (e.g., "21.8mm of precipitation").
- If a metric is null, state that data is unavailable for it that day.
- If a metric key is absent from a record, do not mention that metric at all.
- Keys ending in "_is_trace" set to true mean the phenomenon occurred in trace
  (below-measurable) amounts — mention it (e.g., "trace precipitation") even if the value is 0.
- Echo station_id and obs_date EXACTLY as given in each input record.

Units for each metric:
{units_legend}

Input records (JSON array):
{records}
"""


class NarrativeItem(BaseModel):
    station_id: str
    obs_date: str  # ISO date echoed back
    narrative: str


def load_config() -> dict:
    with open(BASE_DIR / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def fetch_expected_elements(con) -> dict[str, set[str]]:
    expected: dict[str, set[str]] = {}
    for station_id, element in con.execute(EXPECTED_SQL).fetchall():
        expected.setdefault(station_id, set()).add(element)
    return expected
    
def fetch_units_legend(con) -> str:
    rows = con.execute(UNITS_SQL).fetchall()
    return "\n".join(f"- {element}: {unit}" for element, unit in rows)


def prune_record(rec: dict, expected_elements: set[str]) -> dict:
    """Case A handling: drop metric keys for elements the station never reports,
    so the narrative does not talk about 'missing' sensors that never existed."""
    pruned = {}
    for key, val in rec.items():
        if key in META_KEYS:
            pruned[key] = val
            continue
        base = key.removesuffix("_is_trace")
        if base in expected_elements:
            pruned[key] = val
    return pruned


def build_records(columns, rows, expected) -> list[dict]:
    records = []
    for row in rows:
        rec = dict(zip(columns, row))
        if isinstance(rec.get("obs_date"), date):
            rec["obs_date"] = rec["obs_date"].isoformat()
        records.append(prune_record(rec, expected.get(rec["station_id"], set())))
    return records


def main() -> int:
    cfg = load_config()
    ncfg = cfg["narratives"]
    con = duckdb.connect(str(BASE_DIR / cfg["paths"]["duckdb_path"]))
    con.execute(DDL)
    expected = fetch_expected_elements(con)
    units_legend = fetch_units_legend(con)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    stalled = 0
    total_inserted = 0

    while True:
        cur = con.execute(PENDING_SQL, [ncfg["batch_size"]])
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        if not rows:
            print(f"[done] no pending records. total inserted this run: {total_inserted}")
            return 0

        records = build_records(columns, rows, expected)
        sent_keys = {(r["station_id"], r["obs_date"]) for r in records}
        prompt = PROMPT_TEMPLATE.format(units_legend=units_legend, records=json.dumps(records, ensure_ascii=False))

        try:
            response = client.models.generate_content(
                model=ncfg["model_name"],
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": list[NarrativeItem],
                },
            )
            items: list[NarrativeItem] = response.parsed or []
        except Exception as exc:
            print(f"[warn] API call failed ({exc}); sleeping {ncfg['retry_seconds']}s")
            time.sleep(ncfg["retry_seconds"])
            continue

        inserted = 0
        for item in items:
            if (item.station_id, item.obs_date) not in sent_keys:
                print(f"[warn] discarding item with unknown key "
                      f"({item.station_id}, {item.obs_date})")
                continue
            con.execute(
                """insert or ignore into main.narratives
                   (station_id, obs_date, narrative, model_name)
                   values (?, ?, ?, ?)""",
                [item.station_id, item.obs_date, item.narrative, ncfg["model_name"]],
            )
            inserted += 1

        total_inserted += inserted
        print(f"[batch] sent={len(records)} received={len(items)} inserted={inserted}")

        # Stall protection: same records failing repeatedly must not loop forever.
        if inserted == 0:
            stalled += 1
            if stalled >= ncfg["max_stalled_batches"]:
                print("[abort] no progress after repeated attempts on the same batch; "
                      "inspect the prompt/model output.")
                return 1
        else:
            stalled = 0

        time.sleep(ncfg["sleep_between_batches_seconds"])


if __name__ == "__main__":
    sys.exit(main())