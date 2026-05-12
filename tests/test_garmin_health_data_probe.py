import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PROBE_PATH = ROOT_DIR / "experiments" / "garmin_health_data_probe.py"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "garmin_health_data_probe",
        PROBE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe_module = _load_probe_module()


class FakeSpec:
    origin = "/tmp/garmin_health_data/__init__.py"


def test_probe_missing_dependency_prints_install_instruction(monkeypatch):
    messages = []
    monkeypatch.setattr(probe_module, "find_provider_module", lambda: None)

    result = probe_module.run_probe(output=messages.append)

    rendered = "\n".join(messages)
    assert result == 2
    assert "garmin-health-data is not installed." in rendered
    assert (
        "pip install -r optional-requirements/garmin-health-data.txt" in rendered
    )
    assert "not part of Stramin runtime" in rendered


def test_probe_installed_dependency_prints_guidance(monkeypatch):
    messages = []
    monkeypatch.setattr(probe_module, "find_provider_module", lambda: FakeSpec())
    monkeypatch.setattr(probe_module, "provider_version", lambda: "1.2.3")

    result = probe_module.run_probe(output=messages.append)

    rendered = "\n".join(messages)
    assert result == 0
    assert "garmin-health-data appears to be installed." in rendered
    assert "Package version: 1.2.3" in rendered
    assert "Keep GarminDB as the production backend." in rendered
    assert "Do not write daily_state.json" in rendered
    assert "Do not send Telegram messages" in rendered
