select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "data_platform"."public_test_failures"."unique_dim_users_user_id"
    
      
    ) dbt_internal_test