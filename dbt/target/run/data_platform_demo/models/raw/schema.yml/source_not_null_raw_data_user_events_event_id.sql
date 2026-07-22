select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "data_platform"."public_test_failures"."source_not_null_raw_data_user_events_event_id"
    
      
    ) dbt_internal_test