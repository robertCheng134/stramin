import argparse
import importlib.metadata
import importlib.util


INSTALL_COMMAND = "pip install -r optional-requirements/garmin-health-data.txt"
MODULE_NAME = "garmin_health_data"


def find_provider_module(module_name=MODULE_NAME):
    return importlib.util.find_spec(module_name)


def provider_version(package_name="garmin-health-data"):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def print_manual_guidance(output=print):
    output("Manual evaluation guidance:")
    output("- Keep GarminDB as the production backend.")
    output("- Do not write daily_state.json from this experiment.")
    output("- Do not send Telegram messages from this experiment.")
    output("- Use throwaway/local output paths for any manual probes.")
    output("- Record bootstrap duration and incremental sync duration.")
    output("- Check whether sleep, HRV, stress, resting HR, and body metrics")
    output("  can map cleanly to Stramin's daily_state contract.")
    output("- Keep credentials outside the repository.")


def run_probe(output=print):
    spec = find_provider_module()
    if spec is None:
        output("garmin-health-data is not installed.")
        output(f"Install it with: {INSTALL_COMMAND}")
        output("This experiment is optional and not part of Stramin runtime.")
        return 2

    output("garmin-health-data appears to be installed.")
    output(f"Package version: {provider_version()}")
    output(f"Module origin: {spec.origin or 'unknown'}")
    output("")
    print_manual_guidance(output)
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Safe, read-only garmin-health-data evaluation probe."
    )
    parser.add_argument(
        "--guidance",
        action="store_true",
        help="Print manual evaluation guidance without importing provider APIs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.guidance:
        print_manual_guidance()
        return 0
    return run_probe()


if __name__ == "__main__":
    raise SystemExit(main())
