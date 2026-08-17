PYTHON := .venv/bin/python

.PHONY: setup download load transform narratives verify all clean

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

download:
	$(PYTHON) ingest/download.py

load:
	$(PYTHON) ingest/load_raw.py

transform:
	cd weather_dbt && ../.venv/bin/dbt deps && ../.venv/bin/dbt build

narratives:
	$(PYTHON) narratives/generate.py

verify:
	$(PYTHON) scripts/verify.py
	
all: download load transform narratives

clean:
	rm -rf data/weather.duckdb weather_dbt/target weather_dbt/dbt_packages