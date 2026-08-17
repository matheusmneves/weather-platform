# Weather Data Platform

Local pipeline that pulls NOAA GHCN-Daily data for airport stations in Canada's 5 largest metro areas, transforms it with dbt on DuckDB, and generates daily weather narratives in bulk with the Gemini API.

A quick note on how this was built: I used an AI assistant as a sparring partner during development. I would debate design options with it before writing code, then make the call, run everything myself and check the results against real data. All the data quality issues documented below were caught by me inspecting actual outputs, not by the initial plan. I can explain and defend any decision in this repo.

## Quickstart

```
git clone <repo> && cd weather-data-platform
make setup
cp .env.example .env      # add your GEMINI_API_KEY
make all
make verify
```

You don't need to activate the venv to use make, the targets call the venv interpreter directly. Only activate it if you want to run the scripts by hand.

Heads up on quota: generating all narratives takes around 150 free tier requests (batches of 25 over ~3.65k station-days). That fits inside a flash-lite daily quota (500 RPD when I wrote this). If you just want a quick evaluation run, shrink the time window via dbt vars, no SQL changes needed:

```
cd weather_dbt && dbt build --vars '{start_date: 2024-01-01, end_date: 2024-03-31}'
```

Also, `make verify` needs exclusive access to the DuckDB file, so run it after generation finishes. DuckDB only allows one writer at a time.

## Architecture

```
NOAA (HTTP) -> ingest/download.py  -> data/raw/            (idempotent, seed-driven)
            -> ingest/load_raw.py  -> DuckDB raw schema    (all varchar, faithful raw)
            -> dbt: staging -> intermediate -> marts       (typing, QA, units, pivot)
            -> narratives/generate.py -> narratives table  (batched, resumable)
```

## Design decisions

**Config lives in one place.** Stations, elements, units and source file schemas are all seeds or YAML. Adding a 6th city is one line in a CSV, and the ingestion script reads the same seed that dbt filters on, so there's no duplicated list to keep in sync. Same for elements: adding or removing one is a seed edit. I ended up demonstrating this in both directions during development (see the WSFG story below).

**The pivot is metadata-driven.** The mart columns are generated at compile time from the NOAA inventory, using dbt_utils.get_column_values over an intermediate model that intersects the inventory with the curated element list, the target stations and the project window. No element names are hardcoded in SQL anywhere. One known limitation: since the column list comes from compile-time introspection, config changes that affect the schema can need two `dbt build` passes to fully settle.

**Units come from the data dictionary, not the challenge prompt.** The challenge doc says values are in tenths. NOAA's own readme says SNOW and SNWD are whole millimeters. Conversion factors live in a curated seed that gets joined in long format before pivoting, so the conversion is element-selective. The same seed also feeds a units legend into the narrative prompt, meaning a new element updates the prompt automatically.

**Quality checks don't destroy data.** Rows flagged by QA are quarantined, never silently dropped. The main mart filters on passed_qa while mart_quality_summary keeps every exclusion visible and countable. Assumptions about the data became tests that fail loudly: the -9999 missing sentinel must never survive staging, and there's a singular test asserting tmax >= tmin. All 23 dbt tests pass.

**Three kinds of absence are treated differently.** If a station never reports an element (per the inventory), the metric is omitted from the narrative prompt entirely. If a value is missing for a day (QA or source gap), the narrative explicitly says data is unavailable. If a value is present and zero, it's stated as fact. The distinction comes from metadata, not guesswork.

**Narrative generation is idempotent.** State is derived from the database itself: an anti-join between the mart and the narratives table (composite PK on station_id + obs_date) tells the script what's still pending. Rate limit failures resume for free. This got tested in practice when a daily quota ran out mid-run and nothing was lost. Batches use structured JSON output where each item has to echo its keys back; items with missing or made-up keys get discarded and naturally show up as pending again. The model itself is a config value.

## Data quality findings

These all came from inspecting real outputs during development.

**1. Four of the five stations stop reporting on 2024-04-28.** I caught this with a per-city coverage check. The raw files ruled out my pipeline, the download timestamps ruled out stale files, and NOAA's own inventory confirmed it (last_year = 2024 for the affected stations, 2025 for Vancouver). Fix was moving the project window to a range where all 5 stations have full coverage, which is a one-line dbt var change.

**2. The SNOW units trap.** Blindly dividing everything by 10, which is what the challenge doc implies, would corrupt snowfall by 10x. I cross-checked with physics: Montreal on 2023-01-25 shows 21.8mm of precipitation against 218mm of snow, which is the classic ~10:1 snow-to-liquid ratio. You only see that ratio if the conversion is element-selective.

**3. WSFG and WDFG got excluded for implausible units.** Under the documented tenths-of-m/s encoding, daily peak gusts would average around 45 m/s (162 km/h) across all five stations, every day, for two years. Not possible. The values are plausible if read as km/h, and there's a uniform 31.0 floor across all stations that looks like a source reporting threshold in km/h. I didn't want to silently re-scale data against the official data dictionary based on a guess, so I excluded both elements via config. One seed edit, fully reversible.

**4. Free tier quotas are per model, per day.** I hit a 20 requests/day limit on one flash model mid-run. The pipeline absorbed it by design: resumable state meant nothing was lost, and switching to a flash-lite model with a 500 RPD quota was one config line. The first 25 narratives carry a different model_name in the table, which I left as is since the column documents provenance honestly.

**5. Exactly 4 station-days are missing, and I traced each one.** A completeness check against a generated calendar found one missing day in 4 of the 5 stations (Ottawa is complete at 731/731). Three are genuine source gaps, no observations exist for those days. The fourth (Calgary 2022-07-14) turned out to be a second-order effect of my own WSFG exclusion: that day the station only reported gust elements, so removing them from the whitelist removed the whole day, since the inner join drops element-empty days by construction. All four days correctly have no narrative. Absence gets reported, never interpolated.

## ELT vs ETL

The rule I followed: only filter at ingestion when acquisition cost makes it necessary. That's the case for the per-station observation downloads (driven by the stations seed). Everything else gets loaded as faithful raw and all selection logic stays in versioned, testable dbt SQL. The metadata files are ~45 MB total, which is nothing for DuckDB.

## Tradeoffs and what I'd do with more time

- Narrative validation. I designed it (extract numbers from each narrative, cross-check against the source mart row within a tolerance, flag divergence, possibly a second LLM pass as judge) but cut it to protect time for the README and the reproduction test.
- Airflow. The Makefile already chains 4 idempotent steps, so a DAG would be a thin wrapper. Every task is safe to retry by construction, which is most of the orchestration work already done.
- Incremental dbt models. The narrative pending-query already applies the same principle, deriving state from the target table.
- The pivot generates a value + _is_trace column pair for every element, but trace only makes sense for precipitation, so tmax_is_trace is always false. Removing it would mean special-casing elements in Jinja, which is exactly the hardcoding this design avoids. I kept it and documented it.
- Narrative style is deliberately factual and a bit monotone. Giving the model more stylistic freedom would read better but raises hallucination risk. For a data platform I'll take factual over flowery.
- Type checking. At one point a `return` statement lost its value during an edit and produced a None-propagation bug that only surfaced at runtime. mypy would have caught it statically. I'd add it to the Makefile.