"""v1 smoke test: 5 mart rows -> 1 Gemini call -> print to terminal."""
import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

con = duckdb.connect(str(BASE_DIR / "data" / "weather.duckdb"), read_only=True)
rows = con.execute("""
    select city, station_id, obs_date, tmax, tmin, prcp
    from main.mart_daily_weather
    order by obs_date desc
    limit 5
""").fetchall()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
prompt = (
    "For each record below, write a one-sentence weather narrative. "
    "Use only the data provided.\n\n" + "\n".join(str(r) for r in rows)
)
response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
print(response.text)