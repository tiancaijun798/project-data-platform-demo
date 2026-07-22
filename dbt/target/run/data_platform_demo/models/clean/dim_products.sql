
  
    

  create  table "data_platform"."public_clean"."dim_products__dbt_tmp"
  
  
    as
  
  (
    -- ==========================================
-- 清洗层: dim_products — 产品维度表
-- ==========================================

WITH product_stats AS (
    SELECT
        product_id,
        COUNT(*) FILTER (WHERE event_type = 'view')    AS total_views,
        COUNT(*) FILTER (WHERE event_type = 'purchase') AS total_purchases,
        COUNT(*) FILTER (WHERE event_type = 'add_to_cart') AS total_add_to_cart,
        COUNT(*)                                        AS total_interactions
    FROM "data_platform"."public_raw"."stg_user_events"
    WHERE product_id != 'unknown'
    GROUP BY product_id
)

SELECT
    product_id,
    total_views,
    total_purchases,
    total_add_to_cart,
    total_interactions,
    CASE
        WHEN total_purchases > 0
        THEN ROUND(total_purchases * 100.0 / NULLIF(total_views, 0), 2)
        ELSE 0
    END AS conversion_rate_pct
FROM product_stats
  );
  