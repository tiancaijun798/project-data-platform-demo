-- ==========================================
-- 原始数据层 Stage: stg_user_events
-- 从 Parquet 加载的原始事件数据
-- ==========================================

WITH source AS (
    SELECT
        event_id,
        user_id,
        event_type,
        product_id,
        timestamp,
        event_ts,
        page,
        referrer,
        duration_ms,
        device,
        browser,
        processed_at,
        processing_date
    FROM {{ source('raw_data', 'user_events') }}
)

SELECT
    event_id,
    user_id,
    LOWER(event_type)           AS event_type,
    COALESCE(product_id, 'unknown') AS product_id,
    event_ts,
    DATE(event_ts)              AS event_date,
    page,
    COALESCE(referrer, 'direct') AS referrer,
    duration_ms,
    device,
    browser,
    processed_at,
    processing_date
FROM source
WHERE event_ts IS NOT NULL
