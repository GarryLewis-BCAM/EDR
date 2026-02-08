import time
import yaml

from ops_agent.state import StateTracker, AgentState
from ops_agent.checks import router_up, nas_probe
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

    state_announced = None

    try:
        while True:
            router_ok = router_up(cfg["router"]["ip"])
            nas_result = nas_probe(cfg["nas"]["ip"]) if router_ok else None
            nas_ok = nas_result.ok if nas_result else False

            if router_ok and nas_ok:
                tracker.record_success()
                state_announced = None
                print(f"[OK] Router + NAS reachable (via {nas_result.method})")
            else:
                if not router_ok:
                    print("[WARN] Router unreachable")
                else:
                    print(f"[WARN] NAS unreachable (router OK) [{nas_result.detail}]")

                tracker.record_failure()

            if tracker.state == AgentState.DEGRADED:
                if tracker.can_attempt_recovery() and tracker.can_act():
                    print("[ACTION] Starting NAS recovery playbook")
                    tracker.mark_action()
                    success = recover_nas(cfg)
                    tracker.record_recovery_attempt()
                    print("[RESULT]", "success" if success else "failed")

                    if not tracker.can_attempt_recovery():
                        tracker.mark_failed()
                        if state_announced != AgentState.RECOVERY_FAILED:
                            print("[STATE] RECOVERY_FAILED (attempt budget exhausted)")
                            state_announced = AgentState.RECOVERY_FAILED

                elif not tracker.can_attempt_recovery():
                    tracker.mark_failed()
                    if state_announced != AgentState.RECOVERY_FAILED:
                        print("[STATE] RECOVERY_FAILED (attempt budget exhausted)")
                        state_announced = AgentState.RECOVERY_FAILED

            time.sleep(cfg["agent"]["check_interval_seconds"])

    except KeyboardInterrupt:
        print("\n[INFO] shutting down")

if __name__ == "__main__":
    main()
