WITH enriched_events AS (
    SELECT
        e.user_id,
        e.event_type,
        e.experiment_group,
        p.category_name
    FROM events AS e
    JOIN products AS p ON e.product_id = p.product_id
),
dimensions AS (
    SELECT 'overall' AS dimension_type, 'all' AS dimension_value, user_id, event_type
    FROM enriched_events
    UNION ALL
    SELECT 'category', category_name, user_id, event_type
    FROM enriched_events
    UNION ALL
    SELECT 'experiment_group', experiment_group, user_id, event_type
    FROM enriched_events
),
funnel AS (
    SELECT
        dimension_type,
        dimension_value,
        COUNT(DISTINCT CASE WHEN event_type = 'view' THEN user_id END) AS view_users,
        COUNT(DISTINCT CASE WHEN event_type = 'click' THEN user_id END) AS click_users,
        COUNT(DISTINCT CASE WHEN event_type = 'add_to_cart' THEN user_id END) AS cart_users,
        COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchase_users,
        SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS view_events,
        SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS click_events,
        SUM(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS cart_events,
        SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchase_events
    FROM dimensions
    GROUP BY dimension_type, dimension_value
)
SELECT
    dimension_type,
    dimension_value,
    view_users,
    click_users,
    cart_users,
    purchase_users,
    view_events,
    click_events,
    cart_events,
    purchase_events,
    ROUND(1.0 * click_events / NULLIF(view_events, 0), 8) AS view_to_click_rate,
    ROUND(1.0 * cart_events / NULLIF(click_events, 0), 8) AS click_to_cart_rate,
    ROUND(1.0 * purchase_events / NULLIF(cart_events, 0), 8) AS cart_to_purchase_rate,
    ROUND(1.0 * purchase_events / NULLIF(view_events, 0), 8) AS view_to_purchase_rate
FROM funnel
ORDER BY
    CASE dimension_type WHEN 'overall' THEN 1 WHEN 'experiment_group' THEN 2 ELSE 3 END,
    dimension_value;
