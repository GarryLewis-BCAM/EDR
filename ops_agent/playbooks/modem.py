def recover_modem(cfg: dict) -> bool:
    """
    Stub for modem recovery.
    When PDU arrives: power-cycle modem outlet, then verify WAN/DNS health.
    For now: respect simulate_only and return True (simulation success).
    """
    simulate = (cfg.get("playbooks", {}) or {}).get("simulate_only", True)
    if simulate:
        print("[SIMULATION] Would power-cycle MODEM outlet")
        return True
    print("[WARN] recover_modem: not implemented (no PDU integration yet)")
    return False
