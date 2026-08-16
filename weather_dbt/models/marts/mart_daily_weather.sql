select
    ts.city,
    st.station_name,
    st.latitude,
    st.longitude,
    st.elevation_m,
    piv.*
from {{ ref('int_daily_pivoted') }} as piv
inner join {{ ref('target_stations') }} as ts
    on piv.station_id = ts.station_id
left join {{ ref('stg_stations') }} as st
    on piv.station_id = st.station_id