select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "data_platform"."public_test_failures"."source_accepted_values_raw_dat_71d88b78ccec556e423984c453534857"
    
      
    ) dbt_internal_test