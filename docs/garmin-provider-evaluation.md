# Garmin Provider Evaluation

This document is for evaluating `garmin-health-data` as a possible future
Garmin ingestion backend.

GarminDB remains Stramin's production Garmin backend. This evaluation must not
replace GarminDB, change the daily pipeline, change Telegram delivery, or add
`garmin-health-data` to production `requirements.txt`.

## Scope

- Research branch: `research/garmin-health-data-eval`
- Optional dependency file:
  `optional-requirements/garmin-health-data.txt`
- Probe script:
  `experiments/garmin_health_data_probe.py`
- No production code should depend on this provider yet.

## Evaluation Checklist

- Bootstrap duration:
  - How long does first setup/import take?
  - Does it require long-running terminal/tmux operation?
- Incremental sync duration:
  - How long does a normal morning refresh take?
  - Can it run safely inside the 09:00-11:00 delivery window?
- Sleep freshness:
  - Is finalized sleep available today or usually yesterday?
  - Is sleep duration easy to map to `daily_state["sleep_hours"]`?
- HRV freshness:
  - Is nightly HRV available reliably?
  - Are baseline low/high values available?
  - Is HRV 5-minute high distinct from nightly average?
- Daily summary/body metrics availability:
  - Resting HR
  - Stress
  - Body Battery or equivalent energy metric
  - Respiratory or other useful recovery metrics
- Raw payload replay capability:
  - Can raw responses be stored and replayed safely for debugging?
  - Can tests use fixtures without real Garmin credentials?
- SQLite schema readability:
  - Is the data model stable and easy to inspect?
  - Are business date columns available?
  - Can rows be ordered without relying on `rowid`?
- Auth stability:
  - How often does authentication break?
  - Are credentials stored outside the repo?
  - Does it avoid printing secrets?
- Ability to produce Stramin `daily_state` contract:
  - `latest_recovery_date`
  - `validation_status`
  - `sleep_hours`
  - `hrv`
  - `stress`
  - `resting_hr`
  - `recovery_state`
  - `decision`
  - `recommendation`
  - `rationale`
- Risks versus current GarminDB backend:
  - API or auth instability
  - Missing finalized daily summaries
  - Harder local inspection
  - Less predictable freshness
  - Weaker replay/debug workflow
  - More fragile dependency surface

## Guardrails

- Do not replace GarminDB during this evaluation.
- Do not modify `automation/run_daily_pipeline.py`.
- Do not modify Telegram behavior.
- Do not modify validation, retry, or duplicate-prevention behavior.
- Do not add `garmin-health-data` to production `requirements.txt`.
- Do not require real Garmin credentials in tests.
- Do not make production code depend on this provider.
