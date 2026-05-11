import shutil
import stat
from pathlib import Path


REQUIRED_ENV_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
DEFAULT_BACKUP_PATH = Path("~/.stramin.env.backup").expanduser()
PLACEHOLDER_VALUES = {
    "your_bot_token_here",
    "your_chat_id_here",
    "changeme",
    "change_me",
}


def _parse_env_file(path):
    values = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _missing_required_keys(env_path):
    values = _parse_env_file(env_path)
    return [
        key
        for key in REQUIRED_ENV_KEYS
        if not values.get(key) or values.get(key) in PLACEHOLDER_VALUES
    ]


def _chmod_private(path):
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def setup_env(project_dir=None, backup_path=None, output=print):
    project_path = Path(project_dir or Path.cwd())
    env_path = project_path / ".env"
    example_path = project_path / ".env.example"
    backup = Path(backup_path).expanduser() if backup_path else DEFAULT_BACKUP_PATH

    created_from = None
    if env_path.exists():
        output(".env already exists; leaving it unchanged.")
    elif backup.exists():
        shutil.copyfile(backup, env_path)
        _chmod_private(env_path)
        created_from = str(backup)
        output("Created .env from ~/.stramin.env.backup.")
    elif example_path.exists():
        shutil.copyfile(example_path, env_path)
        _chmod_private(env_path)
        created_from = str(example_path)
        output("Created .env from .env.example.")
        output("Next steps:")
        output("- Edit .env and fill in TELEGRAM_BOT_TOKEN.")
        output("- Edit .env and fill in TELEGRAM_CHAT_ID.")
        output("- Keep .env private; do not commit it.")
    else:
        output("Unable to create .env: .env.example was not found.")
        return {
            "status": "failed",
            "env_path": str(env_path),
            "created": False,
            "created_from": None,
            "missing_keys": list(REQUIRED_ENV_KEYS),
        }

    missing_keys = _missing_required_keys(env_path)
    if missing_keys:
        output(
            "Missing required .env values: "
            + ", ".join(missing_keys)
            + "."
        )
        output("No secret values were printed.")
        status = "missing_required_values"
    else:
        output("Required Telegram environment values are present.")
        status = "ready"

    return {
        "status": status,
        "env_path": str(env_path),
        "created": created_from is not None,
        "created_from": created_from,
        "missing_keys": missing_keys,
    }


def main():
    result = setup_env()
    if result["status"] == "failed":
        return 1
    if result["status"] == "missing_required_values":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
