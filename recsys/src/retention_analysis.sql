WITH bounds AS (
    SELECT MAX(event_timestamp) AS observation_end
    FROM events
),
first_activity AS (
    SELECT user_id, MIN(event_timestamp) AS first_active_at
    FROM events
    GROUP BY user_id
),
user_windows AS (
    SELECT
        f.user_id,
        f.first_active_at,
        date(
            f.first_active_at,
            '-' || ((CAST(strftime('%w', f.first_active_at) AS INTEGER) + 6) % 7) || ' days'
        ) AS cohort,
        MAX(CASE
            WHEN julianday(e.event_timestamp) - julianday(f.first_active_at) >= 7
             AND julianday(e.event_timestamp) - julianday(f.first_active_at) < 14
            THEN 1 ELSE 0 END) AS returned_week_1,
        MAX(CASE
            WHEN julianday(e.event_timestamp) - julianday(f.first_active_at) >= 14
             AND julianday(e.event_timestamp) - julianday(f.first_active_at) < 21
            THEN 1 ELSE 0 END) AS returned_week_2,
        CASE WHEN julianday(b.observation_end) - julianday(f.first_active_at) >= 14 THEN 1 ELSE 0 END AS eligible_week_1,
        CASE WHEN julianday(b.observation_end) - julianday(f.first_active_at) >= 21 THEN 1 ELSE 0 END AS eligible_week_2
    FROM first_activity AS f
    JOIN events AS e ON f.user_id = e.user_id
    CROSS JOIN bounds AS b
    GROUP BY f.user_id, f.first_active_at, cohort, b.observation_end
)
SELECT
    cohort,
    COUNT(*) AS users,
    SUM(eligible_week_1) AS week_1_eligible_users,
    SUM(CASE WHEN eligible_week_1 = 1 THEN returned_week_1 ELSE 0 END) AS week_1_returned_users,
    ROUND(
        1.0 * SUM(CASE WHEN eligible_week_1 = 1 THEN returned_week_1 ELSE 0 END)
        / NULLIF(SUM(eligible_week_1), 0),
        8
    ) AS week_1_retention,
    SUM(eligible_week_2) AS week_2_eligible_users,
    SUM(CASE WHEN eligible_week_2 = 1 THEN returned_week_2 ELSE 0 END) AS week_2_returned_users,
    ROUND(
        1.0 * SUM(CASE WHEN eligible_week_2 = 1 THEN returned_week_2 ELSE 0 END)
        / NULLIF(SUM(eligible_week_2), 0),
        8
    ) AS week_2_retention
FROM user_windows
GROUP BY cohort
ORDER BY cohort;
