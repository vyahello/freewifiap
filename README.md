```
███████╗██████╗ ███████╗███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝   W i F i   A P
█████╗  ██████╔╝█████╗  █████╗     ─────────────────────────────────────────
██╔══╝  ██╔══██╗██╔══╝  ██╔══╝     Security Awareness Honeypot
██║     ██║  ██║███████╗███████╗   ⚠  Educational use — authorise first  ⚠
╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝
```

---

## What This Project Does

**FreeWifi** creates a realistic-looking open Wi-Fi hotspot that shows every connecting device a **security warning page** instead of granting internet access. Its purpose is to make people aware — in a visceral, immediate way — that connecting to unknown free Wi-Fi is dangerous.

When a device joins the network:

1. It is issued a DHCP lease and redirected to a captive portal (HTTP port 80).
2. The portal displays a full-screen warning: *"Free Wi-Fi can steal your login."*
3. The operator sees a live console log entry with the device's IP, MAC address, vendor, OS, and browser engine.
4. Everything is written to `devices.log` for later review.

No internet traffic is forwarded. No credentials are captured. The goal is **awareness**, not attack.

---

## Why Free Wi-Fi Is Dangerous

Public and unknown Wi-Fi hotspots are one of the most common vectors for:

| Threat | What happens |
|---|---|
| **Credential theft** | Passwords sent over HTTP are visible to the AP operator in plain text |
| **Traffic sniffing** | An attacker can capture all unencrypted traffic on the network |
| **Evil twin / fake hotspot** | A rogue AP mimics a trusted network name to lure victims |
| **Session hijacking** | Cookies and tokens transmitted over HTTP can be stolen and replayed |
| **HTTPS downgrade (SSLstrip)** | Some tools strip TLS so victims never notice |

Simply connecting to a network — before you visit any website — already leaks your device name, MAC address, and OS to the operator. **This tool makes that visible.**

---

## Requirements

| Dependency | Purpose |
|---|---|
| `hostapd` | Creates the Wi-Fi access point |
| `dnsmasq` | DHCP server + DNS redirect |
| `python3` | Captive portal web server |
| `iptables` | Redirects HTTP traffic to the portal |
| `iw`, `ip`, `ss` | Interface management |
| `ieee-data` (`oui.txt`) | MAC vendor lookup |
| A wireless card that supports **AP mode** | Check with `iw list \| grep "AP"` |

Install on Kali / Debian:

```bash
sudo apt install hostapd dnsmasq ieee-data python3
```

---

## Usage

> **Root is required.** All commands below must be run with `sudo`.

### Open network + captive portal (recommended for demos)

```bash
sudo bash start_free_ap.sh
```

Every connecting device is redirected to the security warning page. No password required to join — just like a real cafe hotspot.

### Open network + login captive portal (credential capture demo)

```bash
sudo bash start_free_ap.sh --secure
```

Runs an open network with a login-style captive portal (`portal.py`) instead of the warning page. When a client connects, they are shown a sign-in form asking for an email/username and password. Submitted credentials are printed to the operator's terminal and appended to `devices.log`. No real internet is forwarded — this demonstrates exactly how an evil-twin portal phishing attack works.

### Stop the AP

Press `Ctrl+C`. The script's `EXIT` trap cleans up `hostapd`, `dnsmasq`, and `iptables` rules, then restarts NetworkManager automatically.

---

## Configuration

Edit the variables at the top of `start_free_ap.sh`:

```bash
IFACE=wlan0          # wireless interface in AP mode
AP_IP=192.168.50.1   # gateway IP served to clients
SSID=FreeWifi        # network name shown to nearby devices
```

---

## What Gets Logged

Every connection and disconnection is appended to `devices.log` (excluded from git). Example entries:

**Default mode** (`welcome.py`):
```
[2025-04-29 14:03:11] CONNECTED    mac=AA:BB:CC:DD:EE:FF  ip=192.168.50.12  vendor=Apple, Inc.  hostname=Janes-iPhone  ...
[2025-04-29 14:03:12] WELCOME_REQUEST ip=192.168.50.12  device=iPhone  os=iOS 17.4  browser_engine=AppleWebKit 605.1 ...
[2025-04-29 14:09:44] DISCONNECTED mac=AA:BB:CC:DD:EE:FF  ip=192.168.50.12  ...
```

**`--secure` mode** (`portal.py`) — also logs captured credentials:
```
[2025-04-29 14:03:11] CONNECTED    mac=AA:BB:CC:DD:EE:FF  ip=192.168.50.12  vendor=Apple, Inc.  hostname=Janes-iPhone  ...
[2025-04-29 14:03:14] PORTAL_REQUEST ip=192.168.50.12  device=iPhone  os=iOS 17.4  ...
[2025-04-29 14:03:21] CREDENTIAL_CAPTURE ip=192.168.50.12  mac=AA:BB:CC:DD:EE:FF  hostname=Janes-iPhone  username='jane@example.com'  password='hunter2'
[2025-04-29 14:09:44] DISCONNECTED mac=AA:BB:CC:DD:EE:FF  ip=192.168.50.12  ...
```

Both portals parse the User-Agent to identify device type, OS version, and browser engine, and correlate it with the DHCP lease for hostname and MAC.

---

## Recovery

If the script crashes or is force-killed and leaves `wlan0` in a broken state:

```bash
sudo bash recover_wlan0.sh
```

This stops any leftover `hostapd`/`dnsmasq` processes, resets the interface to managed mode, and restarts NetworkManager.

---

## Project Structure

```
freewifiap/
├── start_free_ap.sh      # main script — sets up the AP and portal
├── welcome.py            # default captive portal (security warning page)
├── portal.py             # --secure captive portal (login form, credential capture)
├── recover_wlan0.sh      # recovery script for a broken wlan0
└── devices.log           # runtime log — gitignored
```

---

## Legal & Ethical Notice

This tool is intended for:

- **Security awareness demonstrations** on networks you own or administer
- **Penetration testing engagements** with written authorisation
- **CTF / lab environments** under controlled conditions
- **Personal education** about wireless network risks

Running a rogue access point against users who have not consented is **illegal** in most jurisdictions. The SSID `FreeWifi` is intentionally generic and non-deceptive — do not rename it to impersonate a real network.

**You are responsible for how you use this tool.**
