# Legacy Snapshot Audit Plan

Purpose:
The legacy_snapshot/ directory exists to preserve prior work without coupling it
into the new ops_agent architecture.

Rules:
- No code is copied directly.
- Patterns may be re-implemented deliberately.
- Files are read-only reference.

Audit Focus Areas:
- Health check patterns (NAS, network, UPS)
- Watchdog / recovery logic (what worked vs what caused loops)
- Alerting and notification flow (Telegram, SMS)
- Overreach areas (what tried to do too much)

Explicitly Out of Scope:
- UI dashboards
- ML training artifacts
- Historical metrics
- One-off scripts

Outcome:
Produce a short list of:
- Patterns to keep
- Patterns to avoid
- Gaps to fill in ops_agent
