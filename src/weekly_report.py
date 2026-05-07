def format_weekly_report(weekly_plan):
    lines = [
        "Weekly Training Plan",
        "--------------------",
        "",
    ]

    for plan_item in weekly_plan:
        lines.extend(
            [
                str(plan_item.get("day")),
                (
                    "Planned: "
                    f"{plan_item.get('planned_activity')} "
                    f"({plan_item.get('original_intensity')})"
                ),
                (
                    "Adjusted: "
                    f"{plan_item.get('adjusted_activity')} "
                    f"({plan_item.get('adjusted_intensity')})"
                ),
                f"Reason: {plan_item.get('adaptation_reason')}",
                "",
            ]
        )

    return "\n".join(lines).rstrip()
