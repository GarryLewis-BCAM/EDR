def recover_nas(simulate: bool = True) -> bool:
    if simulate:
        print("[SIMULATION] Would power-cycle NAS outlet")
        return True
    return False
