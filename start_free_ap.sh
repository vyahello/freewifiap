#!/usr/bin/env bash
set -e

IFACE=wlan0
AP_IP=192.168.50.1
SSID=FreeWifi
PASSWORD=JmilPass   # hardcoded WPA2 password (min 8 chars)

# Usage:
#   sudo bash start_free_ap.sh           → open network + warning captive portal
#   sudo bash start_free_ap.sh --secure  → WPA2 + warning captive portal
USE_PASSWORD=false
USE_PORTAL=true
for arg in "$@"; do
    [ "$arg" = "--secure" ] && USE_PASSWORD=true
done
HOSTAPD_CONF=/tmp/hostapd_hotspot.conf
DNSMASQ_CONF=/tmp/dnsmasq_hotspot.conf
LEASE_FILE=/tmp/hotspot.leases
LOG_FILE="$(dirname "$0")/devices.log"
OUI_DB=/usr/share/ieee-data/oui.txt

# ── helpers ──────────────────────────────────────────────────────────────────

BOLD=$'\033[1m'
RESET=$'\033[0m'

file_log() { echo "$@" >> "$LOG_FILE"; }

console_client() {
    local action="$1"
    local device="$2"
    local ip="$3"
    local mac="$4"
    local os="${5:-unknown}"
    local browser_engine="${6:-unknown}"
    printf '[%s] %s device=%b%s%b  ip=%s  mac=%s  os=%s  browser_engine=%s\n' \
        "$(date '+%H:%M:%S')" "$action" "$BOLD" "$device" "$RESET" "$ip" "$mac" "$os" "$browser_engine"
}

die() {
    echo "[!] $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

preflight() {
    [ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash $0"
    [ -d "/sys/class/net/$IFACE" ] || die "Interface not found: $IFACE"

    for cmd in hostapd dnsmasq ip iw systemctl awk sed grep xargs ss; do
        need_cmd "$cmd"
    done

    $USE_PORTAL && need_cmd python3
}

is_randomized_mac() {
    # locally-administered bit (bit 1 of first byte) = randomized/private MAC
    local first_byte=$((16#${1:0:2}))
    (( first_byte & 0x02 ))
}

vendor_lookup() {
    local mac="${1^^}"
    if is_randomized_mac "$mac"; then
        echo "Randomized/Private MAC"
        return
    fi
    local prefix="${mac:0:2}-${mac:3:2}-${mac:6:2}"
    # OUI file has \r\n endings and double tabs; strip both
    local vendor
    vendor=$(grep -m1 "^${prefix}" "$OUI_DB" 2>/dev/null \
        | sed 's/.*\t\t//' | tr -d '\r' | xargs)
    echo "${vendor:-Unknown}"
}

get_ip() {
    # dnsmasq lease format: expiry  mac  ip  hostname  client-id
    local mac="${1,,}"
    local ip=""
    for _ in 1 2 3 4 5; do
        ip=$(awk -v m="$mac" 'tolower($2)==m {print $3}' "$LEASE_FILE" 2>/dev/null | head -1)
        [ -n "$ip" ] && echo "$ip" && return
        sleep 1
    done
    echo "pending"
}

lease_info() {
    # dnsmasq lease format: expiry  mac  ip  hostname  client-id
    local mac="${1,,}"
    awk -v m="$mac" '
        tolower($2)==m {
            printf "lease_expiry=%s  hostname=%s  client_id=%s", $1, $4, $5
            found=1
            exit
        }
        END {
            if (!found) printf "lease_expiry=pending  hostname=pending  client_id=pending"
        }
    ' "$LEASE_FILE" 2>/dev/null
}

neighbor_info() {
    local ip="$1"
    [ -z "$ip" ] || [ "$ip" = "pending" ] && {
        echo "neighbor=pending"
        return
    }

    local neighbor
    neighbor=$(ip neigh show "$ip" dev "$IFACE" 2>/dev/null | xargs)
    echo "neighbor=${neighbor:-unknown}"
}

station_info() {
    iw dev "$IFACE" station get "$1" 2>/dev/null \
        | awk '
            BEGIN { first=1 }
            /^[[:space:]]*Station[[:space:]]/ { next }
            /^[[:space:]]*$/ { next }
            {
                line=$0
                sub(/^[[:space:]]+/, "", line)
                key=line
                sub(/:.*/, "", key)
                value=line
                sub(/^[^:]+:[[:space:]]*/, "", value)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
                gsub(/[^A-Za-z0-9]+/, "_", key)
                gsub(/^_+|_+$/, "", key)
                key=tolower(key)
                if (key == "") next
                printf "%s%s=%s", first ? "" : "  ", key, value
                first=0
            }
            END {
                if (first) printf "station=unavailable"
            }
        '
}

monitor_events() {
    local ap_mac
    ap_mac=$(cat /sys/class/net/"$IFACE"/address 2>/dev/null | tr '[:lower:]' '[:upper:]')

    while IFS= read -r line; do
        file_log "[$(date '+%Y-%m-%d %H:%M:%S')] HOSTAPD $line"

        if [[ "$line" =~ AP-STA-CONNECTED[[:space:]]([0-9a-fA-F:]{17}) ]]; then
            MAC="${BASH_REMATCH[1]}"
            # skip the AP's own MAC (appears in hostapd startup lines)
            [[ "${MAC^^}" == "$ap_mac" ]] && continue
            IP=$(get_ip "$MAC")
            VENDOR=$(vendor_lookup "$MAC")
            LEASE=$(lease_info "$MAC")
            NEIGHBOR=$(neighbor_info "$IP")
            STATION=$(station_info "$MAC")
            HOSTNAME=$(awk -v m="${MAC,,}" 'tolower($2)==m {print $4}' "$LEASE_FILE" 2>/dev/null | head -1)
            DEVICE="${HOSTNAME:-$VENDOR}"
            file_log "[$(date '+%Y-%m-%d %H:%M:%S')] CONNECTED    mac=$MAC  ip=$IP  vendor=$VENDOR  $LEASE  $NEIGHBOR  $STATION"
            $USE_PORTAL || console_client "CONNECTED" "$DEVICE" "$IP" "$MAC"

        elif [[ "$line" =~ AP-STA-DISCONNECTED[[:space:]]([0-9a-fA-F:]{17}) ]]; then
            MAC="${BASH_REMATCH[1]}"
            [[ "${MAC^^}" == "$ap_mac" ]] && continue
            IP=$(awk -v m="${MAC,,}" 'tolower($2)==m {print $3}' "$LEASE_FILE" 2>/dev/null | head -1)
            LEASE=$(lease_info "$MAC")
            NEIGHBOR=$(neighbor_info "$IP")
            HOSTNAME=$(awk -v m="${MAC,,}" 'tolower($2)==m {print $4}' "$LEASE_FILE" 2>/dev/null | head -1)
            VENDOR=$(vendor_lookup "$MAC")
            DEVICE="${HOSTNAME:-$VENDOR}"
            file_log "[$(date '+%Y-%m-%d %H:%M:%S')] DISCONNECTED mac=$MAC  ip=${IP:-unknown}  $LEASE  $NEIGHBOR"
            console_client "DISCONNECTED" "$DEVICE" "${IP:-unknown}" "$MAC"
        fi
    done
}

# ── cleanup ───────────────────────────────────────────────────────────────────

portal_iptables() {
    local action=$1   # -A or -D
    # port 80 only — redirecting 443 sends a corrupted TLS response which iOS
    # treats as "broken network" rather than "captive portal"; let HTTPS fail
    # naturally (connection refused) so iOS falls back to the HTTP probe
    iptables -t nat "$action" PREROUTING -i "$IFACE" -p tcp --dport 80 -j DNAT --to-destination "$AP_IP:80" 2>/dev/null || true
}

stop_leftovers() {
    pkill hostapd 2>/dev/null || true
    pkill dnsmasq 2>/dev/null || true
    pkill -f portal.py 2>/dev/null || true
    pkill -f welcome.py 2>/dev/null || true
    portal_iptables -D
}

cleanup() {
    echo ""
    echo "[*] Stopping AP..."
    pkill hostapd  2>/dev/null || true
    pkill dnsmasq  2>/dev/null || true
    pkill -f portal.py 2>/dev/null || true
    pkill -f welcome.py 2>/dev/null || true
    $USE_PORTAL && portal_iptables -D || true
    ip addr flush dev "$IFACE"
    systemctl start NetworkManager
    echo "[+] Done. NetworkManager restarted."
    echo "[+] Device log: $LOG_FILE"
}
trap cleanup EXIT

# ── configs ───────────────────────────────────────────────────────────────────

echo "[*] Writing configs..."
preflight

if $USE_PASSWORD; then
    cat > "$HOSTAPD_CONF" << EOF
interface=$IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF
else
    cat > "$HOSTAPD_CONF" << EOF
interface=$IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF
fi

if $USE_PORTAL; then
    cat > "$DNSMASQ_CONF" << EOF
interface=$IFACE
dhcp-range=192.168.50.10,192.168.50.50,255.255.255.0,12h
dhcp-option=3,$AP_IP
dhcp-option=6,$AP_IP
dhcp-option=114,"http://$AP_IP/"
dhcp-leasefile=$LEASE_FILE
log-dhcp
log-queries
log-facility=$LOG_FILE
address=/#/$AP_IP
EOF
else
    cat > "$DNSMASQ_CONF" << EOF
interface=$IFACE
dhcp-range=192.168.50.10,192.168.50.50,255.255.255.0,12h
dhcp-option=3,$AP_IP
dhcp-option=6,$AP_IP
dhcp-leasefile=$LEASE_FILE
log-dhcp
log-queries
log-facility=$LOG_FILE
EOF
fi

> "$LOG_FILE"
> "$LEASE_FILE"

# ── start ─────────────────────────────────────────────────────────────────────

echo "[*] Stopping NetworkManager..."
systemctl stop NetworkManager
stop_leftovers

echo "[*] Configuring interface..."
ip link set "$IFACE" up
ip addr flush dev "$IFACE"
ip addr add "$AP_IP/24" dev "$IFACE"

echo "[*] Starting hostapd..."
hostapd "$HOSTAPD_CONF" 2>&1 | monitor_events &

for _ in $(seq 1 20); do
    if iw dev "$IFACE" info 2>/dev/null | grep -q "type AP"; then
        break
    fi
    pgrep -x hostapd >/dev/null || die "hostapd exited before the AP became ready"
    sleep 0.5
done
iw dev "$IFACE" info 2>/dev/null | grep -q "type AP" || die "hostapd did not put $IFACE into AP mode"

if $USE_PORTAL; then
    fuser -k 80/tcp 2>/dev/null || true
    echo "[*] Starting captive portal..."
    python3 "$(dirname "$0")/welcome.py" "$AP_IP" "$LOG_FILE" "$LEASE_FILE" &
    # wait until portal is actually listening before dnsmasq gives out IPs —
    # iOS fires the CNA probe the moment it gets a DHCP lease; if the portal
    # isn't ready yet iOS gets connection-refused, marks "no portal", never retries
    for i in $(seq 1 10); do
        ss -tlnp | grep -q ":80 " && break
        sleep 0.5
    done
    ss -tlnp | grep -q ":80 " || die "welcome.py did not start listening on port 80"
    echo "[*] Adding iptables rules (port 80 → portal)..."
    portal_iptables -A
fi

echo "[*] Starting dnsmasq..."
dnsmasq --conf-file="$DNSMASQ_CONF" --no-daemon --log-async >/dev/null 2>>"$LOG_FILE" &
sleep 0.5
pgrep -x dnsmasq >/dev/null || die "dnsmasq exited before it could serve DHCP"

$USE_PASSWORD && echo "[+] Security: WPA2  password=$PASSWORD" || echo "[+] Security: open (no password)"
$USE_PORTAL   && echo "[+] Portal:   http://$AP_IP  (warning page; all HTTP redirected here)" || true
echo "[+] AP '$SSID' is up at $AP_IP. Press Ctrl+C to stop."
echo "[+] Device log: $LOG_FILE"
wait
