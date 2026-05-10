import argparse

from common import DEFAULT_LOG_DIR, ensure_log_dir, get_file_logger, now_iso


def sync_garmindb(log_dir=DEFAULT_LOG_DIR):
    """Record the sync step without running GarminDB automatically.

    v4 keeps GarminDB sync operator-controlled. The preferred command is:
    garmindb_cli.py --all --download --import --analyze --latest
    """

    ensure_log_dir(log_dir)
    logger = get_file_logger("garmindb-sync", log_dir)
    logger.info("GarminDB sync step started")
    logger.info("GarminDB sync is manual in v4; no sync command was executed")

    return {
        "status": "skipped_manual_sync_required",
        "started_at": now_iso(),
        "message": (
            "GarminDB sync is manual in v4. Run "
            "garmindb_cli.py --all --download --import --analyze --latest in tmux."
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Record GarminDB sync skeleton step.")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    return parser.parse_args()


def main():
    args = parse_args()
    result = sync_garmindb(log_dir=args.log_dir)
    print(result["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

