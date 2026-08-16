select
    trim(country_code) as country_code,
    trim(country_name) as country_name
from {{ source('raw', 'ghcnd_countries') }}