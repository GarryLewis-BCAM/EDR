import platform
import re
import socket
import subprocess
from typing import Optional

def ping(ip: str, timeout: int = 1) -> bool:
    try:
        # macOS ping uses -W (ms on some versions), Linux uses -W (seconds).
        # We'll keep it simple; it's best-effort.
        subprocess.check_output(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False

def tcp_connect(ip: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def arp_seen(ip: str) -> bool:
    """
    Returns True if the OS neighbor/ARP cache has a resolved entry for the IP.
    This is useful when ICMP is blocked but the device is present on LAN.
    """
    system = platform.system().lower()

    try:
        if "darwin" in system or "mac" in system:
            # Example: "? (192.168.1.80) at aa:bb:cc:dd:ee:ff on en0 ..."
            out = subprocess.check_output(["arp", "-n", ip], stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
            return "(incomplete)" not in out and re.search(r"\bat\s+([0-9a-f]{1,2}:){5}[0-9a-f]{1,2}\b", out, re.I) is not None

        # Linux: `ip neigh show 192.168.1.80` -> "... lladdr aa:bb... REACHABLE"
        out = subprocess.check_output(["ip", "neigh", "show", ip], stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        if "FAILED" in out.upper() or "INCOMPLETE" in out.upper():
            return False
        return re.search(r"\blladdr\s+([0-9a-f]{1,2}:){5}[0-9a-f]{1,2}\b", out, re.I) is not None

    except Exception:
        return False

def router_up(router_ip: str) -> bool:
    # Router should answer ping normally
    return ping(router_ip)

def nas_up(nas_ip: str) -> bool:
    # 1) ICMP
    if ping(nas_ip):
        return True

    # 2) SMB/TCP is often a better liveness signal than ICMP
    if tcp_connect(nas_ip, 445, timeout=1.0):
        return True

    # 3) ARP/neighbor cache detection (best-effort)
    if arp_seen(nas_ip):
        return True

    return False
