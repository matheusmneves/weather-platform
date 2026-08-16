select distinct
    inv.station_id,
    inv.element
from {{ ref('stg_inventory') }} as inv
inner join {{ ref('target_stations') }} as ts
    on inv.station_id = ts.station_id
inner join {{ ref('element_config') }} as cfg
    on inv.element = cfg.element
where inv.last_year >= cast(substr('{{ var("start_date") }}', 1, 4) as integer)
    and inv.first_year <= cast(substr('{{ var("end_date") }}', 1, 4) as integer)