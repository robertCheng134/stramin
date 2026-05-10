import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
DEFAULT_DB_DIR = Path("~/HealthData/DBs").expanduser()
DEFAULT_LOG_DIR = ROOT_DIR / "logs"
DEFAULT_STATE_PATH = ROOT_DIR / "daily_state.json"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def ensure_log_dir(log_dir=DEFAULT_LOG_DIR):
    path = Path(log_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_logger(name, log_dir=DEFAULT_LOG_DIR):
    log_path = ensure_log_dir(log_dir) / f"{name}.log"
    logger = logging.getLogger(f"stramin.automation.{name}")
    logger.setLevel(logging.INFO)

    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logger.addHandler(handler)

    return logger


def today_iso():
    return date.today().isoformat()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json_atomic(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(target.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as state_file:
        json.dump(data, state_file, ensure_ascii=False, indent=2)
        state_file.write("\n")
    temp_path.replace(target)
    return target
