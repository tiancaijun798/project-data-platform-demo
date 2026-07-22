select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "data_platform"."public_test_failures"."not_null_fct_user_events_daily_event_type"
    
      
    ) dbt_internal_test