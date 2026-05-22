import os


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "zh-TW"}


MESSAGES = {
    "en": {
        "common.unavailable": "unavailable",
        "report.title": "Stramin Daily Recovery",
        "report.recovery_date": "Recovery date",
        "report.finalized_data": "Latest finalized Garmin recovery data is from {date}.",
        "report.garmin_recovery": "Garmin recovery",
        "report.sleep": "Sleep",
        "report.hrv": "HRV",
        "report.stress": "Stress",
        "report.resting_hr": "Resting HR",
        "report.recovery_status": "Recovery status",
        "report.today_recommendation": "Today's recommendation",
        "report.intensity": "Intensity",
        "report.suggested_activity": "Suggested activity",
        "report.plan": "Plan",
        "report.why": "Why",
        "warning.title": "Stramin Daily Report Delayed",
        "warning.no_recommendation": "No training recommendation was sent.",
        "warning.reason": "Reason",
        "bot.unauthorized_chat": "Unauthorized chat.",
        "bot.start": (
            "Welcome to stramin.\n\n"
            "Garmin CSV is the primary health data source. "
            "Use /entry to add today's metrics, /today for today's recommendation, "
            "or /weekly for the weekly plan."
        ),
        "bot.help": (
            "stramin Telegram Bot\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/help - Show available commands\n"
            "/today - Generate today's Garmin-first recovery recommendation\n"
            "/weekly - Generate the weekly adaptive training plan\n"
            "/entry - Enter today's Garmin health data\n"
            "/cancel - Cancel the current entry flow"
        ),
        "bot.unknown_command": "Unknown command. Use /help to see available commands.",
        "bot.entry_requires_chat": "Entry flow requires a Telegram chat.",
        "bot.entry_start": (
            "Starting Garmin entry for {date}.\n"
            "Send /cancel anytime to stop.\n\n"
            "{prompt}"
        ),
        "bot.entry_saved": (
            "Garmin health entry saved.\n\n"
            "Today's recommendation:\n\n"
            "{recommendation}"
        ),
        "bot.entry_saved_recommendation_failed": (
            "Garmin health entry saved, but recommendation failed: {error}"
        ),
        "bot.entry_canceled": "Entry canceled.",
        "bot.entry_no_active": "No active entry flow to cancel.",
        "bot.help_hint": "Send /help to see available commands.",
        "entry.sleep_hours": "Enter sleep_hours (0-24, decimal allowed):",
        "entry.hrv_status": "Enter hrv_status (balanced, low, poor, unbalanced):",
        "entry.body_battery": "Enter body_battery (0-100):",
        "entry.resting_hr": "Enter resting_hr (20-120):",
        "entry.stress": "Enter stress (optional, send '-' to skip):",
    },
    "zh-TW": {
        "common.unavailable": "無資料",
        "report.title": "Stramin 每日恢復",
        "report.recovery_date": "恢復日期",
        "report.finalized_data": "Garmin 最新完成整理的恢復資料來自 {date}。",
        "report.garmin_recovery": "Garmin 恢復指標",
        "report.sleep": "睡眠",
        "report.hrv": "HRV",
        "report.stress": "壓力",
        "report.resting_hr": "靜息心率",
        "report.recovery_status": "恢復狀態",
        "report.today_recommendation": "今日建議",
        "report.intensity": "強度",
        "report.suggested_activity": "建議活動",
        "report.plan": "計畫",
        "report.why": "為什麼",
        "warning.title": "Stramin 每日報告延遲",
        "warning.no_recommendation": "未發送訓練建議。",
        "warning.reason": "原因",
        "bot.unauthorized_chat": "未授權的聊天室。",
        "bot.start": (
            "歡迎使用 stramin。\n\n"
            "Garmin CSV 是主要健康資料來源。"
            "使用 /entry 新增今日指標，/today 查看今日建議，"
            "或 /weekly 查看每週計畫。"
        ),
        "bot.help": (
            "stramin Telegram 機器人\n\n"
            "指令:\n"
            "/start - 開始使用\n"
            "/help - 顯示可用指令\n"
            "/today - 產生今日 Garmin-first 恢復建議\n"
            "/weekly - 產生每週自適應訓練計畫\n"
            "/entry - 輸入今日 Garmin 健康資料\n"
            "/cancel - 取消目前輸入流程"
        ),
        "bot.unknown_command": "未知指令。使用 /help 查看可用指令。",
        "bot.entry_requires_chat": "輸入流程需要 Telegram 聊天室。",
        "bot.entry_start": (
            "開始輸入 {date} 的 Garmin 資料。\n"
            "隨時可送出 /cancel 取消。\n\n"
            "{prompt}"
        ),
        "bot.entry_saved": (
            "Garmin 健康資料已儲存。\n\n"
            "今日建議:\n\n"
            "{recommendation}"
        ),
        "bot.entry_saved_recommendation_failed": (
            "Garmin 健康資料已儲存，但產生建議失敗: {error}"
        ),
        "bot.entry_canceled": "輸入已取消。",
        "bot.entry_no_active": "目前沒有進行中的輸入流程。",
        "bot.help_hint": "送出 /help 查看可用指令。",
        "entry.sleep_hours": "請輸入 sleep_hours（0-24，可用小數）:",
        "entry.hrv_status": "請輸入 hrv_status（balanced, low, poor, unbalanced）:",
        "entry.body_battery": "請輸入 body_battery（0-100）:",
        "entry.resting_hr": "請輸入 resting_hr（20-120）:",
        "entry.stress": "請輸入 stress（選填，送出 '-' 可略過）:",
    },
}


def current_language():
    configured = os.getenv("STRAMIN_LANGUAGE", DEFAULT_LANGUAGE).strip()
    for language in SUPPORTED_LANGUAGES:
        if configured.lower() == language.lower():
            return language
    return DEFAULT_LANGUAGE


def localized_text(key, **kwargs):
    language = current_language()
    template = MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE]).get(
        key,
        MESSAGES[DEFAULT_LANGUAGE].get(key, key),
    )
    return template.format(**kwargs) if kwargs else template
