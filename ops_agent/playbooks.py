from ops_agent.power.controller import SimulatedPowerController, PowerController

def build_power_controller(cfg: dict) -> PowerController:
    # For now, always simulated. Later we’ll switch based on cfg["power"]["provider"].
    return SimulatedPowerController()

def recover_nas(cfg: dict) -> bool:
    """
    NAS recovery playbook.
    Current action: power-cycle NAS outlet (once) when real PDU is enabled.
    """
    simulate = cfg["playbooks"]["simulate_only"]
    nas_outlet = cfg.get("power", {}).get("nas_outlet_id")

    if simulate:
        print("[SIMULATION] Would power-cycle NAS outlet (no hardware)")
        return True

    if not nas_outlet:
        print("[ERROR] power.nas_outlet_id not set in config; cannot power-cycle")
        return False

    controller = build_power_controller(cfg)
    result = controller.power_cycle(int(nas_outlet), off_seconds=30)
    print(result.message)
    return result.ok
