# Direct Ethernet Connection to NAS

## Why This Works
Travel/hotel WiFi often has "client isolation" that prevents devices from seeing each other. A direct ethernet cable bypasses this.

## Steps

### 1. Physical Connection
- Connect ethernet cable between Mac and NAS
- Mac will auto-configure a link-local address (169.254.x.x)

### 2. Find NAS on Ethernet Interface
```bash
# After connecting cable, run:
ifconfig en6  # or en7, en8 depending on your adapter
arp -a | grep "90:9:d0:8e:e0:d7"  # Find NAS by MAC address
```

### 3. Access DSM via New IP
The NAS will have a new IP on the ethernet interface. Look for it in the arp output, typically:
- `169.254.x.x` (link-local)
- Or a self-assigned `192.168.x.x`

### 4. Run Automation
```bash
# Update NAS_IP in script to the new ethernet IP
cd ~/Security/hybrid-edr/nas-deployment-clean/
export NAS_IP="<ethernet_ip_here>"
./complete_nas_edr.sh
```

## Alternative: USB Ethernet Adapter
If your Mac doesn't have ethernet, use a USB-C to ethernet adapter.
