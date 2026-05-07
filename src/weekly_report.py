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
                f"- activity: {plan_item.get('activity')}",
                f"- intensity: {plan_item.get('intensity')}",
                f"- reason: {plan_item.get('reason')}",
                "",
            ]
        )

    return "\n".join(lines).rstrip()
