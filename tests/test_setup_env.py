import importlib.util
import stat
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SETUP_ENV_PATH = ROOT_DIR / "automation" / "setup_env.py"


def _load_setup_env_module():
    spec = importlib.util.spec_from_file_location("setup_env", SETUP_ENV_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_env_module = _load_setup_env_module()


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_setup_env_does_not_overwrite_existing_env(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TELEGRAM_BOT_TOKEN=existing-token\n"
        "TELEGRAM_CHAT_ID=123\n"
        "GARMIN_EMAIL=user@example.com\n"
        "GARMIN_PASSWORD=existing-password\n",
        encoding="utf-8",
    )
    backup_path = tmp_path / ".stramin.env.backup"
    backup_path.write_text(
        "TELEGRAM_BOT_TOKEN=backup-token\nTELEGRAM_CHAT_ID=456\n",
        encoding="utf-8",
    )
    messages = []

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=backup_path,
        output=messages.append,
    )

    assert result["status"] == "ready"
    assert result["created"] is False
    assert "existing-token" in env_path.read_text(encoding="utf-8")
    assert "backup-token" not in env_path.read_text(encoding="utf-8")
    assert ".env already exists" in messages[0]
    assert "GARMINDB_DIR=~/HealthData/DBs" in env_path.read_text(encoding="utf-8")
    assert "GARMINDB_PATH=~/HealthData/DBs/garmin.db" in env_path.read_text(
        encoding="utf-8"
    )


def test_setup_env_restores_from_backup_and_chmods_private(tmp_path):
    backup_path = tmp_path / ".stramin.env.backup"
    backup_path.write_text(
        "TELEGRAM_BOT_TOKEN=backup-token\n"
        "TELEGRAM_CHAT_ID=7157240394\n"
        "GARMIN_EMAIL=user@example.com\n"
        "GARMIN_PASSWORD=backup-password\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text(
        "TELEGRAM_BOT_TOKEN=your_bot_token_here\n"
        "TELEGRAM_CHAT_ID=your_chat_id_here\n",
        encoding="utf-8",
    )
    messages = []

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=backup_path,
        output=messages.append,
    )

    env_path = tmp_path / ".env"
    assert result["status"] == "ready"
    assert result["created"] is True
    assert result["created_from"] == str(backup_path)
    env_text = env_path.read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=backup-token" in env_text
    assert "TELEGRAM_CHAT_ID=7157240394" in env_text
    assert "GARMIN_EMAIL=user@example.com" in env_text
    assert "GARMIN_PASSWORD=backup-password" in env_text
    assert "GARMINDB_DIR=~/HealthData/DBs" in env_text
    assert _mode(env_path) == 0o600
    assert "backup-token" not in "\n".join(messages)
    assert "7157240394" not in "\n".join(messages)


def test_setup_env_creates_from_example_and_prints_next_steps(tmp_path):
    (tmp_path / ".env.example").write_text(
        "TELEGRAM_BOT_TOKEN=your_bot_token_here\n"
        "TELEGRAM_CHAT_ID=your_chat_id_here\n",
        encoding="utf-8",
    )
    messages = []

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=tmp_path / "missing-backup",
        output=messages.append,
    )

    env_path = tmp_path / ".env"
    assert result["status"] == "missing_required_values"
    assert result["created"] is True
    assert result["missing_keys"] == [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GARMIN_EMAIL",
        "GARMIN_PASSWORD",
    ]
    assert env_path.exists()
    assert _mode(env_path) == 0o600
    assert (
        "Missing required .env values: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, "
        "GARMIN_EMAIL, GARMIN_PASSWORD."
    ) in messages


def test_setup_env_reports_missing_required_values_without_printing_secrets(tmp_path):
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=secret-token\n",
        encoding="utf-8",
    )
    messages = []

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=tmp_path / "missing-backup",
        output=messages.append,
    )

    rendered = "\n".join(messages)
    assert result["status"] == "missing_required_values"
    assert result["missing_keys"] == [
        "TELEGRAM_CHAT_ID",
        "GARMIN_EMAIL",
        "GARMIN_PASSWORD",
    ]
    assert "secret-token" not in rendered
    assert "TELEGRAM_CHAT_ID" in rendered


def test_setup_env_interactive_prompts_only_for_secrets_and_writes_backup(tmp_path):
    backup_path = tmp_path / ".stramin.env.backup"
    (tmp_path / ".env.example").write_text("", encoding="utf-8")
    answers = iter(
        [
            "telegram-token",
            "7157240394",
            "user@example.com",
            "",
            "",
        ]
    )
    password_prompts = []
    messages = []

    def input_fn(prompt):
        assert "GARMINDB" not in prompt
        return next(answers)

    def password_fn(prompt):
        assert prompt.startswith("GARMIN_PASSWORD")
        password_prompts.append(prompt)
        return "garmin-password"

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=backup_path,
        output=messages.append,
        interactive=True,
        input_fn=input_fn,
        password_fn=password_fn,
    )

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    rendered = "\n".join(messages)
    assert result["status"] == "ready"
    assert password_prompts
    assert "TELEGRAM_BOT_TOKEN=telegram-token" in env_text
    assert "TELEGRAM_CHAT_ID=7157240394" in env_text
    assert "GARMIN_EMAIL=user@example.com" in env_text
    assert "GARMIN_PASSWORD=garmin-password" in env_text
    assert "GARMINDB_DIR=~/HealthData/DBs" in env_text
    assert "GARMINDB_PATH=~/HealthData/DBs/garmin.db" in env_text
    assert backup_path.read_text(encoding="utf-8") == env_text
    assert "telegram-token" not in rendered
    assert "garmin-password" not in rendered
    assert _mode(tmp_path / ".env") == 0o600
    assert _mode(backup_path) == 0o600


def test_setup_env_interactive_preserves_existing_values_without_confirmation(
    tmp_path,
):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TELEGRAM_BOT_TOKEN=existing-token\n"
        "TELEGRAM_CHAT_ID=existing-chat\n"
        "GARMIN_EMAIL=existing@example.com\n"
        "GARMIN_PASSWORD=existing-password\n",
        encoding="utf-8",
    )
    backup_path = tmp_path / ".stramin.env.backup"
    answers = iter(["n", "n", "n", "n", "", ""])

    result = setup_env_module.setup_env(
        project_dir=tmp_path,
        backup_path=backup_path,
        output=lambda message: None,
        interactive=True,
        input_fn=lambda prompt: next(answers),
        password_fn=lambda prompt: "new-password",
    )

    env_text = env_path.read_text(encoding="utf-8")
    assert result["status"] == "ready"
    assert "TELEGRAM_BOT_TOKEN=existing-token" in env_text
    assert "TELEGRAM_CHAT_ID=existing-chat" in env_text
    assert "GARMIN_EMAIL=existing@example.com" in env_text
    assert "GARMIN_PASSWORD=existing-password" in env_text
    assert "new-password" not in env_text
