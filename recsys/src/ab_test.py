"""Analyze the randomized experiment with a two-proportion z-test."""

import csv
import math
import sqlite3
from typing import Dict

from scipy.stats import norm

from config import DATABASE_PATH, RESULTS


def analyze_ab_test() -> Dict[str, object]:
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        rows = connection.execute(
            """
            SELECT
                u.experiment_group,
                COUNT(*) AS users,
                SUM(CASE WHEN purchased.user_id IS NOT NULL THEN 1 ELSE 0 END) AS converted_users
            FROM users AS u
            LEFT JOIN (
                SELECT DISTINCT user_id
                FROM events
                WHERE event_type = 'purchase'
            ) AS purchased ON u.user_id = purchased.user_id
            GROUP BY u.experiment_group
            ORDER BY u.experiment_group
            """
        ).fetchall()
    finally:
        connection.close()

    counts = {group: (int(users), int(converted)) for group, users, converted in rows}
    control_users, control_converted = counts["control"]
    treatment_users, treatment_converted = counts["treatment"]
    control_rate = control_converted / control_users
    treatment_rate = treatment_converted / treatment_users
    absolute_uplift = treatment_rate - control_rate
    relative_uplift = absolute_uplift / control_rate

    pooled_rate = (control_converted + treatment_converted) / (control_users + treatment_users)
    null_standard_error = math.sqrt(
        pooled_rate * (1.0 - pooled_rate) * (1.0 / control_users + 1.0 / treatment_users)
    )
    z_statistic = absolute_uplift / null_standard_error
    p_value = 2.0 * norm.sf(abs(z_statistic))

    # The confidence interval uses the unpooled standard error for the observed
    # difference in independent binomial proportions.
    interval_standard_error = math.sqrt(
        control_rate * (1.0 - control_rate) / control_users
        + treatment_rate * (1.0 - treatment_rate) / treatment_users
    )
    critical_value = norm.ppf(0.975)
    ci_lower = absolute_uplift - critical_value * interval_standard_error
    ci_upper = absolute_uplift + critical_value * interval_standard_error

    result: Dict[str, object] = {
        "metric": "user_purchase_conversion",
        "control_users": control_users,
        "treatment_users": treatment_users,
        "control_converted_users": control_converted,
        "treatment_converted_users": treatment_converted,
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_uplift": absolute_uplift,
        "relative_uplift": relative_uplift,
        "z_statistic": z_statistic,
        "p_value": p_value,
        "ci_95_lower": ci_lower,
        "ci_95_upper": ci_upper,
        "statistically_significant_0_05": p_value < 0.05,
    }
    output_path = RESULTS / "ab_test_results.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)
    return result


if __name__ == "__main__":
    print(analyze_ab_test())
