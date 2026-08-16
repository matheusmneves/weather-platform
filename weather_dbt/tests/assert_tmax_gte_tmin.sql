-- singular test: fails if any day has tmax < tmin.
select station_id, obs_date, tmax, tmin
from {{ ref('mart_daily_weather') }}
where tmax is not null
  and tmin is not null
  and tmax < tmin