-- v1: intentionally hardcoded to get end-to-end working
select
    station_id,
    obs_date,
    max(case when element = 'TMAX' then value end) / 10.0 as tmax,
    max(case when element = 'TMIN' then value end) / 10.0 as tmin,
    max(case when element = 'PRCP' then value end) / 10.0 as prcp
from {{ ref('stg_observations') }}
where passed_qa
group by 1, 2