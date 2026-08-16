-- quarantine visibility: every qa flagged row, counted by station/month/element/flag
-- nothing is silently dropped: rows excluded from mart_daily_weather are accounted for here
select
    station_id,
    element,
    date_trunc('month', obs_date) as observation_month,
    qflag,
    count(*) as flagged_rows
from {{ ref('stg_observations') }}
where not passed_qa
group by 1, 2, 3, 4
order by flagged_rows desc