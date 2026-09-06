-- ==========================================
-- 清洗层: fct_user_events_daily — 每日事件汇总
-- ==========================================

WITH daily_stats AS (
    SELECT
        event_date,
        event_type,
        COUNT(*)                    AS total_events,
        COUNT(DISTINCT user_id)     AS unique_users,
        ROUND(AVG(COALESCE(duration_ms, 0)::numeric), 0)::bigint AS avg_duration_ms,
        ROUND(SUM(COALESCE(duration_ms, 0)::numeric) / 1000.0, 2) AS total_duration_seconds
    FROM {{ ref('stg_user_events') }}
    GROUP BY event_date, event_type
)

SELECT
    event_date,
    event_type,
    total_events,
    unique_users,
    avg_duration_ms,
    total_duration_seconds
FROM daily_stats
