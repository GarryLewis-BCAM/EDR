import time
from dataclasses import dataclass

@dataclass(frozen=True)
class PowerActionResult:
    ok: bool
    message: str

class PowerController:
    """
    Interface for power control (PDU, smart plug, etc).
    Implementations must be deterministic and return structured results.
    """
    def power_off(self, outlet_id: int) -> PowerActionResult:
        raise NotImplementedError

    def power_on(self, outlet_id: int) -> PowerActionResult:
        raise NotImplementedError

    def power_cycle(self, outlet_id: int, off_seconds: int = 30) -> PowerActionResult:
        r1 = self.power_off(outlet_id)
        if not r1.ok:
            return r1
        time.sleep(max(1, int(off_seconds)))
        r2 = self.power_on(outlet_id)
        return r2

class SimulatedPowerController(PowerController):
    def power_off(self, outlet_id: int) -> PowerActionResult:
        return PowerActionResult(True, f"[SIMULATION] Would power OFF outlet {outlet_id}")

    def power_on(self, outlet_id: int) -> PowerActionResult:
        return PowerActionResult(True, f"[SIMULATION] Would power ON outlet {outlet_id}")
