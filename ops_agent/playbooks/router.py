def recover_router(cfg: dict) -> bool:
    """
    Stub for router recovery.
    When PDU arrives: power-cycle router outlet, then verify gateway reachable.
    For now: respect simulate_only and return True (simulation success).
    """
    simulate = (cfg.get("playbooks", {}) or {}).get("simulate_only", True)
    if simulate:
        print("[SIMULATION] Would power-cycle ROUTER outlet")
        return True
    print("[WARN] recover_router: not implemented (no PDU integration yet)")
    return False
