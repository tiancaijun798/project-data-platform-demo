-- ==========================================
-- 清洗层: dim_users — 用户维度表
-- ==========================================

WITH user_activity AS (
    SELECT
        user_id,
        MIN(event_date) AS first_seen_at,
        MAX(event_date) AS last_seen_at,
        COUNT(*)        AS total_events
    FROM {{ ref('stg_user_events') }}
    GROUP BY user_id
)

SELECT
    user_id,
    first_seen_at,
    last_seen_at,
    total_events,
    CASE
        WHEN total_events >= 50 THEN 'power_user'
        WHEN total_events >= 10 THEN 'active'
        WHEN total_events >= 2  THEN 'regular'
        ELSE 'new'
    END AS user_segment
FROM user_activity
