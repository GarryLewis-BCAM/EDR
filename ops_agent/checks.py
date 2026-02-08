import platform
import re
import socket
import subprocess
from dataclasses import dataclass

@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    method: str
    detail: str = ""

def ping_probe(ip: str, timeout: int = 1) -> ProbeResult:
    try:
        subprocess.check_output(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stderr=subprocess.DEVNULL
        )
        return ProbeResult(True, "ping", f"{ip} replied")
    except Exception as e:
        return ProbeResult(False, "ping", "no reply")

def tcp_probe(ip: str, port: int, timeout: float = 1.0) -> ProbeResult:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return ProbeResult(True, f"tcp:{port}", "connect ok")
    except Exception:
        return ProbeResult(False, f"tcp:{port}", "connect failed")

def arp_probe(ip: str) -> ProbeResult:
    system = platform.system().lower()

    try:
        if "darwin" in system or "mac" in system:
            out = subprocess.check_output(["arp", "-n", ip], stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
            if "(incomplete)" in out:
                return ProbeResult(False, "arp", "incomplete")
            ok = re.search(r"\bat\s+([0-9a-f]{1,2}:){5}[0-9a-f]{1,2}\b", out, re.I) is not None
            return ProbeResult(ok, "arp", "mac present" if ok else "no mac")

        out = subprocess.check_output(["ip", "neigh", "show", ip], stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        if "FAILED" in out.upper() or "INCOMPLETE" in out.upper():
            return ProbeResult(False, "neigh", "incomplete/failed")
        ok = re.search(r"\blladdr\s+([0-9a-f]{1,2}:){5}[0-9a-f]{1,2}\b", out, re.I) is not None
        return ProbeResult(ok, "neigh", "lladdr present" if ok else "no lladdr")

    except Exception:
        return ProbeResult(False, "arp", "probe error")

def router_up(router_ip: str) -> bool:
    r = ping_probe(router_ip)
    if r.ok:
        return True
    # fallbacks: many routers answer on DNS or web even if ICMP is restricted
    if tcp_probe(router_ip, 53, timeout=1.0).ok:
        return True
    if tcp_probe(router_ip, 80, timeout=1.0).ok:
        return True
    return False

def nas_probe(nas_ip: str) -> ProbeResult:
    r1 = ping_probe(nas_ip)
    if r1.ok:
        return r1

    r2 = tcp_probe(nas_ip, 445, timeout=1.0)
    if r2.ok:
        return r2

    r3 = arp_probe(nas_ip)
    if r3.ok:
        return r3

    # Return the “best” failure detail (prefer tcp over ping over arp)
    return ProbeResult(False, "down", f"{r1.method}:{r1.detail}, {r2.method}:{r2.detail}, {r3.method}:{r3.detail}")

def nas_up(nas_ip: str) -> bool:
    return nas_probe(nas_ip).ok

# --- LOCAL gateway discovery (added) ---
def get_default_gateway():
    """
    Returns the default IPv4 gateway as seen by the OS (macOS).
    """
    try:
        out = subprocess.check_output(
            ["route", "-n", "get", "default"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.splitlines():
            if line.strip().startswith("gateway:"):
                return line.split()[-1]
    except Exception:
        pass
    return None

def lan_router_up() -> bool:
    """
    True if the local LAN gateway is reachable.
    Avoids false negatives caused by VPN/tunnel route hijacks.
    """
    gw = get_default_gateway()
    if not gw:
        return False

    # 1) ICMP
    if ping_probe(gw).ok:
        return True

    # 2) TCP fallbacks (routers often answer these even if ICMP blocked)
    try:
        if tcp_probe(gw, 53, timeout=1.0).ok:
            return True
        if tcp_probe(gw, 80, timeout=1.0).ok:
            return True
    except Exception:
        pass

    return False

def gateway_interface(gateway_ip: str):
    """
    Returns the interface name used to reach a specific IP (macOS).
    Example: 'en0', 'utun2', etc.
    """
    try:
        out = subprocess.check_output(
            ["route", "-n", "get", gateway_ip],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.splitlines():
            if line.strip().startswith("interface:"):
                return line.split()[-1]
    except Exception:
        pass
    return None

def local_context():
    """
    Returns one of:
      - LOCAL_OK
      - LOCAL_DOWN
      - VPN_HIJACK
      - UNKNOWN
    """
    gw = get_default_gateway()
    if not gw:
        return ("UNKNOWN", None, None)

    iface = gateway_interface(gw)

    # If gateway route goes via tunnel, you're "logically remote" from LAN
    if iface and iface.startswith("utun"):
        return ("VPN_HIJACK", gw, iface)

    if lan_router_up():
        return ("LOCAL_OK", gw, iface or "unknown")

    return ("LOCAL_DOWN", gw, iface or "unknown")
