import argparse
import getpass
import shutil
import stat
from pathlib import Path


REQUIRED_ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GARMIN_EMAIL",
    "GARMIN_PASSWORD",
)
OPTIONAL_ENV_KEYS = ("OPENAI_API_KEY", "STRAVA_ACCESS_TOKEN")
GARMINDB_DEFAULTS = {
    "GARMINDB_DIR": "~/HealthData/DBs",
    "GARMINDB_PATH": "~/HealthData/DBs/garmin.db",
}
DEFAULT_BACKUP_PATH = Path("~/.stramin.env.backup").expanduser()
PLACEHOLDER_VALUES = {
    "your_bot_token_here",
    "your_chat_id_here",
    "your_key_here",
    "your_token_here",
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
    return _missing_required_keys_from_values(values)


def _missing_required_keys_from_values(values):
    return [
        key
        for key in REQUIRED_ENV_KEYS
        if not values.get(key) or values.get(key) in PLACEHOLDER_VALUES
    ]


def _chmod_private(path):
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _write_env_file(path, values):
    ordered_keys = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GARMIN_EMAIL",
        "GARMIN_PASSWORD",
        "GARMINDB_DIR",
        "GARMINDB_PATH",
        "OPENAI_API_KEY",
        "STRAVA_ACCESS_TOKEN",
    ]
    lines = []
    written = set()
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
            written.add(key)
    for key in sorted(values):
        if key not in written:
            lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _chmod_private(path)


def _copy_env_file(source, target):
    shutil.copyfile(source, target)
    _chmod_private(target)


def _is_set(value):
    return bool(value) and value not in PLACEHOLDER_VALUES


def _confirm_replace(key, input_fn, output):
    answer = input_fn(f"{key} already exists. Replace it? [y/N]: ").strip().lower()
    if answer == "y":
        return True
    output(f"Keeping existing {key}.")
    return False


def _prompt_value(key, values, input_fn, password_fn, output, optional=False):
    current = values.get(key, "")
    if _is_set(current):
        if not _confirm_replace(key, input_fn, output):
            return

    prompt = f"{key}"
    if optional:
        prompt += " (optional, press Enter to skip)"
    prompt += ": "

    if key == "GARMIN_PASSWORD":
        value = password_fn(prompt).strip()
    else:
        value = input_fn(prompt).strip()

    if value:
        values[key] = value
    elif not optional:
        output(f"{key} is required.")


def _run_interactive_setup(values, input_fn, password_fn, output):
    output("Interactive Stramin setup")
    output("Enter user-owned secrets. Values will not be printed.")
    for key in REQUIRED_ENV_KEYS:
        while not _is_set(values.get(key, "")):
            _prompt_value(key, values, input_fn, password_fn, output)
    for key in OPTIONAL_ENV_KEYS:
        _prompt_value(key, values, input_fn, password_fn, output, optional=True)


def _apply_garmindb_defaults(values):
    for key, value in GARMINDB_DEFAULTS.items():
        if not _is_set(values.get(key, "")):
            values[key] = value


def _backup_env(env_path, backup_path):
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(env_path, backup_path)
    _chmod_private(backup_path)


def setup_env(
    project_dir=None,
    backup_path=None,
    output=print,
    interactive=False,
    input_fn=input,
    password_fn=getpass.getpass,
):
    project_path = Path(project_dir or Path.cwd())
    env_path = project_path / ".env"
    example_path = project_path / ".env.example"
    backup = Path(backup_path).expanduser() if backup_path else DEFAULT_BACKUP_PATH

    created_from = None
    if env_path.exists():
        output(".env already exists; preserving existing values.")
        values = _parse_env_file(env_path)
    elif backup.exists():
        _copy_env_file(backup, env_path)
        created_from = str(backup)
        output("Created .env from ~/.stramin.env.backup.")
        values = _parse_env_file(env_path)
    elif example_path.exists():
        _copy_env_file(example_path, env_path)
        created_from = str(example_path)
        output("Created .env from .env.example.")
        values = _parse_env_file(env_path)
    else:
        output("Unable to create .env: .env.example was not found.")
        return {
            "status": "failed",
            "env_path": str(env_path),
            "created": False,
            "created_from": None,
            "missing_keys": list(REQUIRED_ENV_KEYS),
        }

    _apply_garmindb_defaults(values)
    if interactive:
        _run_interactive_setup(values, input_fn, password_fn, output)
    _write_env_file(env_path, values)

    missing_keys = _missing_required_keys_from_values(values)
    if missing_keys:
        output(
            "Missing required .env values: "
            + ", ".join(missing_keys)
            + "."
        )
        output("No secret values were printed.")
        status = "missing_required_values"
    else:
        _backup_env(env_path, backup)
        output("Required Stramin environment values are present.")
        output("Updated ~/.stramin.env.backup for future installs.")
        status = "ready"

    return {
        "status": status,
        "env_path": str(env_path),
        "created": created_from is not None,
        "created_from": created_from,
        "missing_keys": missing_keys,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Create or validate Stramin .env.")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for Telegram, Garmin, and optional integration secrets.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success even when required values still need to be filled in.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    result = setup_env(interactive=args.interactive)
    if result["status"] == "failed":
        return 1
    if result["status"] == "missing_required_values" and not args.allow_missing:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
