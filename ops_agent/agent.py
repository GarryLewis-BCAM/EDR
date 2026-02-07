import time
import yaml

from ops_agent.state import StateTracker, AgentState
from ops_agent.checks import router_up, nas_up
from ops_agent.playbooks import recover_nas

CONFIG_PATH = "config/ops_agent.local.yaml"

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def main():
    cfg = load_config()

    max_attempts = cfg.get("agent", {}).get("max_attempts_per_incident", 1)

    tracker = StateTracker(
        failure_threshold=cfg["agent"]["failure_threshold"],
        cooldown_seconds=cfg["agent"]["cooldown_minutes"] * 60,
        max_attempts_per_incident=max_attempts,
    )

    try:
        while True:
            router_ok = router_up(cfg["router"]["ip"])
            nas_ok = nas_up(cfg["nas"]["ip"]) if router_ok else False

            if router_ok and nas_ok:
                tracker.record_success()
                print("[OK] Router + NAS reachable")
            else:
                # clearer logging
                if not router_ok:
                    print("[WARN] Router unreachable")
                else:
                    print("[WARN] NAS unreachable (router OK)")

                tracker.record_failure()

            # If we are degraded, try recovery if allowed.
            if tracker.state == AgentState.DEGRADED:
                if not tracker.can_attempt_recovery():
                    # Budget exhausted; mark failed once and stop trying until recovery.
                    if tracker.state != AgentState.RECOVERY_FAILED:
                        tracker.mark_failed()
                    print("[STATE] RECOVERY_FAILED (attempt budget exhausted)")
                elif tracker.can_act():
                    print("[ACTION] Starting NAS recovery playbook")
                    tracker.mark_action()
                    success = recover_nas(simulate=cfg["playbooks"]["simulate_only"])
                    tracker.record_recovery_attempt()
                    print("[RESULT]", "success" if success else "failed")

                    # If budget now exhausted, mark failed; agent will remain quiet until OK.
                    if not tracker.can_attempt_recovery():
                        tracker.mark_failed()
                        print("[STATE] RECOVERY_FAILED (attempt budget exhausted)")

            time.sleep(cfg["agent"]["check_interval_seconds"])

    except KeyboardInterrupt:
        print("\n[INFO] shutting down")

if __name__ == "__main__":
    main()
