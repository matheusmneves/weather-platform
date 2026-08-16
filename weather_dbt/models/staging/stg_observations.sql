with source as (

    select * from {{ source('raw', 'observations') }}

),

renamed as (

    select
        station_id,
        -- raw date is YYYYMMDD
        coalesce(
            try_cast(observation_date as date),
            try_strptime(observation_date, '%Y%m%d')::date
        )       as obs_date,
        element,
        try_cast(value as integer) as value_raw,
        nullif(trim(coalesce(m_flag, '')), '') as mflag,
        nullif(trim(coalesce(q_flag, '')), '') as qflag,
        nullif(trim(coalesce(s_flag, '')), '') as sflag
    from source

),

cleaned as (

    select
        station_id,
        obs_date,
        element,
        nullif(value_raw, -9999) as value,   -- documented missing sentinel
        mflag,
        qflag,
        sflag,
        (qflag is null) as passed_qa         -- blank qflag = passed all QA checks
    from renamed

)

select *
from cleaned
where obs_date between '{{ var("start_date") }}' and '{{ var("end_date") }}'