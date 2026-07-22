
    
    

with all_values as (

    select
        event_type as value_field,
        count(*) as n_records

    from "data_platform"."raw"."user_events"
    group by event_type

)

select *
from all_values
where value_field not in (
    'click','view','add_to_cart','purchase','search','logout'
)


