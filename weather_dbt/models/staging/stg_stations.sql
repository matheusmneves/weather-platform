select
    trim(station_id)                                as station_id,
    try_cast(latitude  as double)                   as latitude,
    try_cast(longitude as double)                   as longitude,
    nullif(try_cast(elevation as double), -999.9)   as elevation_m,
    nullif(trim(coalesce(state, '')), '')           as state,
    trim(station_name)                              as station_name,
    nullif(trim(coalesce(wmo_id, '')), '')          as wmo_id
from {{ source('raw', 'ghcnd_stations') }}