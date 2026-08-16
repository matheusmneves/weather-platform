-- unit conversion via curated element_config seed (units documented in NOAA readme.txt)
-- the inner join doubles as the curated element whitelist
select
    obs.station_id,
    obs.obs_date,
    obs.element,
    obs.value / cfg.scale_divisor as value_converted,
    (obs.mflag = 'T')             as is_trace,
    cfg.unit
from {{ ref('stg_observations') }} as obs
inner join {{ ref('element_config') }} as cfg
    on obs.element = cfg.element
inner join {{ ref('target_stations') }} as ts
    on obs.station_id = ts.station_id
where obs.passed_qa