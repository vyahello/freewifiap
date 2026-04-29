#!/usr/bin/env bash
# Run this if start_ap.sh crashed or was force-killed and wlan0 is broken.

IFACE=wlan0

echo "[*] Killing hostapd and dnsmasq..."
pkill hostapd 2>/dev/null && echo "    hostapd stopped" || echo "    hostapd was not running"
pkill dnsmasq 2>/dev/null && echo "    dnsmasq stopped" || echo "    dnsmasq was not running"

echo "[*] Resetting $IFACE..."
ip addr flush dev "$IFACE"
ip link set "$IFACE" down
iw dev "$IFACE" set type managed
ip link set "$IFACE" up

echo "[*] Starting NetworkManager..."
systemctl start NetworkManager

echo "[*] Waiting for NetworkManager to reconnect..."
for i in $(seq 1 15); do
    STATE=$(nmcli -t -f STATE general 2>/dev/null)
    if [ "$STATE" = "connected" ]; then
        echo "[+] Connected! $(nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | head -1)"
        exit 0
    fi
    sleep 1
    printf "    attempt %d/15...\r" "$i"
done

echo ""
echo "[!] NetworkManager started but not connected yet."
echo "    Try manually: nmcli dev wifi connect <SSID> password <PASSWORD>"
echo "    Or check status: nmcli dev status"
