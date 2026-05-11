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
        "TELEGRAM_BOT_TOKEN=existing-token\nTELEGRAM_CHAT_ID=123\n",
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


def test_setup_env_restores_from_backup_and_chmods_private(tmp_path):
    backup_path = tmp_path / ".stramin.env.backup"
    backup_path.write_text(
        "TELEGRAM_BOT_TOKEN=backup-token\nTELEGRAM_CHAT_ID=7157240394\n",
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
    assert env_path.read_text(encoding="utf-8") == backup_path.read_text(
        encoding="utf-8"
    )
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
    assert result["missing_keys"] == ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    assert env_path.exists()
    assert _mode(env_path) == 0o600
    assert "Next steps:" in messages
    assert "Missing required .env values: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID." in (
        messages
    )


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
    assert result["missing_keys"] == ["TELEGRAM_CHAT_ID"]
    assert "secret-token" not in rendered
    assert "TELEGRAM_CHAT_ID" in rendered
