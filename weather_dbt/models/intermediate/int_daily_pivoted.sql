-- metadata-driven pivot: the column list is generated at compile time from int_station_elements (inventory ∩ curated config ∩ target stations)
-- adding a 6th city or a new element = config change only, zero SQL edits

{% set elements = dbt_utils.get_column_values(
    table=ref('int_station_elements'),
    column='element',
    order_by='element'
) %}

select
    station_id,
    obs_date,
    {% for element in elements %}
    max(case when element = '{{ element }}' then value_converted end)
        as {{ element | lower }},
    max(case when element = '{{ element }}' then is_trace end)
        as {{ element | lower }}_is_trace{{ "," if not loop.last }}
    {% endfor %}
from {{ ref('int_observations_converted') }}
group by 1, 2