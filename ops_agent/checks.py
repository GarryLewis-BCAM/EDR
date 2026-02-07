import subprocess

def ping(ip: str, timeout: int = 1) -> bool:
    try:
        subprocess.check_output(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False

def router_up(router_ip: str) -> bool:
    return ping(router_ip)

def nas_up(nas_ip: str) -> bool:
    return ping(nas_ip)
