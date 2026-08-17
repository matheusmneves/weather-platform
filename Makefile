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
	$(PYTHON) -c "import duckdb; con = duckdb.connect('data/weather.duckdb', read_only=True); \
	print(con.execute('select (select count(*) from main.narratives) as narratives, (select count(*) from main.mart_daily_weather) as mart_rows').df()); \
	print(con.execute('select city, count(*) as days, min(obs_date) as first_day, max(obs_date) as last_day from main.mart_daily_weather group by city order by city').df())"

all: download load transform narratives

clean:
	rm -rf data/weather.duckdb weather_dbt/target weather_dbt/dbt_packages