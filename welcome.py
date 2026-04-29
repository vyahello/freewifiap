#!/usr/bin/env python3

"""Safety-focused captive portal web server for JmilAP hotspot.
Usage: python3 welcome.py [ap_ip]   (default: 192.168.50.1)
"""

import http.server
import re
import socketserver
import sys
import urllib.parse
from datetime import datetime

PORT = 80
AP_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.50.1"
LOG_FILE = sys.argv[2] if len(sys.argv) > 2 else None
LEASE_FILE = sys.argv[3] if len(sys.argv) > 3 else None
BOLD = "\033[1m"
RESET = "\033[0m"
SEEN_CLIENTS = set()

WELCOME_PAGE = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Free Wi-Fi Security Warning</title>
    <style>
        * {{ box-sizing: border-box; }}
        html {{ min-height: 100%; background: #050608; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: Arial, Helvetica, sans-serif;
            color: #f5f7fa;
            background:
                radial-gradient(circle at 50% 48%, rgba(255, 0, 45, .24), transparent 20rem),
                radial-gradient(circle at 20% 18%, rgba(0, 255, 140, .15), transparent 28rem),
                radial-gradient(circle at 82% 14%, rgba(255, 0, 45, .16), transparent 22rem),
                linear-gradient(135deg, #050203 0%, #130407 45%, #020303 100%);
            display: grid;
            place-items: center;
            padding: 28px 16px;
        }}
        main {{
            width: min(100%, 1080px);
            display: grid;
            grid-template-columns: minmax(0, 1.05fr) minmax(300px, .95fr);
            gap: 42px;
            align-items: center;
        }}
        .warning {{
            min-width: 0;
        }}
        .kicker {{
            display: inline-block;
            margin: 0 0 18px;
            padding: 7px 11px;
            border: 1px solid rgba(255, 30, 60, .9);
            color: #ffdce2;
            background: rgba(255, 0, 45, .2);
            box-shadow: 0 0 22px rgba(255, 0, 45, .18);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
        }}
        h1 {{
            margin: 0;
            max-width: 820px;
            font-size: clamp(38px, 7vw, 78px);
            line-height: 1;
            font-weight: 900;
            letter-spacing: 0;
        }}
        h1 strong {{
            color: #ff1e3c;
            text-shadow: 0 0 28px rgba(255, 0, 45, .5);
        }}
        .lead {{
            margin: 24px 0 0;
            max-width: 780px;
            font-size: clamp(20px, 3vw, 30px);
            line-height: 1.25;
            font-weight: 800;
        }}
        .lead strong {{
            color: #ff4f6f;
            text-shadow: 0 0 18px rgba(255, 79, 111, .28);
        }}
        .labels {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 26px;
        }}
        .label {{
            display: inline-flex;
            align-items: center;
            min-height: 38px;
            padding: 0 13px;
            border: 1px solid rgba(255, 30, 60, .7);
            background: rgba(255, 0, 45, .16);
            color: #ffdce2;
            font-size: 14px;
            font-weight: 900;
            text-transform: uppercase;
            box-shadow: inset 0 0 18px rgba(255, 0, 45, .08);
        }}
        .art {{
            position: relative;
            min-height: 540px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, .12);
            background:
                radial-gradient(circle at 50% 58%, rgba(255, 0, 45, .28), transparent 16rem),
                radial-gradient(circle at 50% 58%, rgba(82, 255, 191, .12), transparent 22rem),
                linear-gradient(rgba(82, 255, 191, .06) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 0, 45, .08) 1px, transparent 1px),
                linear-gradient(180deg, #130407 0%, #020303 100%);
            background-size: 22px 22px, 22px 22px, auto;
            box-shadow: 0 28px 80px rgba(0, 0, 0, .42);
        }}
        .art::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(
                180deg,
                rgba(255,30,60,.08) 0,
                rgba(255,30,60,.08) 1px,
                transparent 1px,
                transparent 5px
            );
            mix-blend-mode: screen;
            pointer-events: none;
        }}
        .moon {{
            position: absolute;
            width: 190px;
            height: 190px;
            right: 44px;
            top: 44px;
            border-radius: 50%;
            background: radial-gradient(circle at 38% 35%, #ffffff, #caffe9 40%, #1b6f59 72%, transparent 73%);
            opacity: .55;
            filter: drop-shadow(0 0 35px rgba(255, 0, 45, .4));
        }}
        .code {{
            position: absolute;
            inset: 36px auto auto 34px;
            width: 220px;
            color: rgba(82, 255, 191, .78);
            font-family: "Courier New", monospace;
            font-size: 16px;
            line-height: 1.35;
            white-space: pre-line;
        }}
        .rain {{
            position: absolute;
            inset: 0;
            display: grid;
            grid-template-columns: repeat(9, 1fr);
            gap: 10px;
            padding: 22px;
            color: rgba(255, 30, 60, .25);
            font-family: "Courier New", monospace;
            font-size: 18px;
            line-height: 1.35;
            overflow: hidden;
            pointer-events: none;
        }}
        .rain span {{
            writing-mode: vertical-rl;
            text-orientation: mixed;
            text-shadow: 0 0 12px rgba(255, 0, 45, .5);
        }}
        .figure {{
            position: absolute;
            left: 50%;
            bottom: 72px;
            width: 290px;
            height: 360px;
            transform: translateX(-50%);
        }}
        .hood {{
            position: absolute;
            left: 24px;
            top: 0;
            width: 242px;
            height: 292px;
            border-radius: 118px 118px 26px 26px;
            background: linear-gradient(135deg, #1d2427, #050608 70%);
            border: 1px solid rgba(255,30,60,.18);
            box-shadow: inset 0 0 48px rgba(0,0,0,.95), 0 30px 46px rgba(0,0,0,.56);
        }}
        .hood::before {{
            content: "";
            position: absolute;
            left: 42px;
            right: 42px;
            top: 24px;
            bottom: 34px;
            border-radius: 80px 80px 24px 24px;
            background: linear-gradient(180deg, rgba(255,0,45,.1), rgba(0,0,0,.68));
            border: 1px solid rgba(255,30,60,.12);
        }}
        .face {{
            position: absolute;
            left: 77px;
            top: 82px;
            width: 136px;
            height: 142px;
            border-radius: 50% 50% 45% 45%;
            background: linear-gradient(180deg, #111820, #050608);
            box-shadow: inset 0 0 28px rgba(0,0,0,.95);
        }}
        .eyes {{
            position: absolute;
            left: 94px;
            top: 132px;
            display: flex;
            gap: 42px;
        }}
        .eyes span {{
            width: 26px;
            height: 7px;
            background: #ff1e3c;
            box-shadow: 0 0 18px rgba(255, 0, 45, .95);
        }}
        .body {{
            position: absolute;
            left: 18px;
            bottom: 0;
            width: 254px;
            height: 166px;
            border-radius: 50px 50px 0 0;
            background: linear-gradient(120deg, #101821, #050608);
            border: 1px solid rgba(255,255,255,.08);
        }}
        .laptop {{
            position: absolute;
            left: -10px;
            right: -10px;
            bottom: 0;
            height: 122px;
            background: linear-gradient(180deg, #1e2a35, #090d11);
            border: 1px solid rgba(255, 30, 60, .38);
            box-shadow: 0 0 30px rgba(255, 0, 45, .26);
        }}
        .laptop::before {{
            content: "PUBLIC_WIFI";
            position: absolute;
            top: 26px;
            left: 50%;
            transform: translateX(-50%);
            color: #ff4f6f;
            font-family: "Courier New", monospace;
            font-size: 18px;
            font-weight: 700;
            text-shadow: 0 0 12px rgba(255, 0, 45, .9);
        }}
        .caption {{
            position: absolute;
            left: 22px;
            right: 22px;
            bottom: 22px;
            margin: 0;
            color: #ffffff;
            background: rgba(0, 0, 0, .58);
            border: 1px solid rgba(255, 30, 60, .7);
            box-shadow: 0 0 22px rgba(255, 0, 45, .18);
            padding: 14px 16px;
            font-size: 18px;
            line-height: 1.35;
            font-weight: 800;
            text-align: center;
        }}
        @media (max-width: 860px) {{
            body {{ place-items: start center; }}
            main {{
                grid-template-columns: 1fr;
                gap: 30px;
            }}
            .art {{
                min-height: 450px;
            }}
            .figure {{
                transform: translateX(-50%) scale(.82);
                transform-origin: bottom center;
            }}
            .moon {{
                width: 140px;
                height: 140px;
                right: 24px;
                top: 24px;
            }}
            .code {{
                width: 170px;
                font-size: 13px;
            }}
        }}
    </style>
</head>
<body>
    <main>
        <section class="warning" aria-label="Free Wi-Fi security warning">
            <p class="kicker">Wi-Fi warning</p>
            <h1><strong>Free Wi-Fi</strong> can steal your login.</h1>
            <p class="lead">
                Never enter passwords on unknown networks. <strong>Your traffic can be sniffed.</strong>
            </p>
            <div class="labels" aria-label="Risk labels">
                <span class="label">Credential theft</span>
                <span class="label">Traffic sniffing</span>
                <span class="label">Fake hotspot</span>
            </div>
        </section>
        <section class="art" aria-label="Cyber security warning illustration">
            <div class="moon" aria-hidden="true"></div>
            <div class="rain" aria-hidden="true">
                <span>01001101010111000101</span>
                <span>access denied 010101</span>
                <span>packet trace 001011</span>
                <span>root shell 101001</span>
                <span>session token 0110</span>
                <span>public wifi 11001</span>
                <span>sniffing blocked 010</span>
                <span>ghost route 10110</span>
                <span>stay offline 00101</span>
            </div>
            <div class="code" aria-hidden="true">unknown AP
credential risk
packet sniffing
disconnect</div>
            <div class="figure" aria-hidden="true">
                <div class="hood"></div>
                <div class="face"></div>
                <div class="eyes"><span></span><span></span></div>
                <div class="body"></div>
                <div class="laptop"></div>
            </div>
            <p class="caption">Do not trust unknown free Wi-Fi. Disconnect.</p>
        </section>
    </main>
</body>
</html>
"""


WELCOME_BYTES = WELCOME_PAGE.encode()


def clean(value):
    return " ".join(str(value).replace("\x00", "").split())


def log_event(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    if not LOG_FILE:
        print(line, flush=True)
        return
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except OSError as exc:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] welcome log error: {exc}", flush=True)


def lease_for_ip(ip):
    if not LEASE_FILE:
        return {"mac": "unknown", "hostname": "unknown", "client_id": "unknown"}
    try:
        with open(LEASE_FILE, encoding="utf-8") as lease_file:
            for line in lease_file:
                parts = line.split()
                if len(parts) >= 5 and parts[2] == ip:
                    return {
                        "mac": parts[1],
                        "hostname": parts[3],
                        "client_id": parts[4],
                    }
    except OSError:
        pass
    return {"mac": "unknown", "hostname": "unknown", "client_id": "unknown"}


def user_agent_info(user_agent):
    ua = user_agent or ""
    webkit_match = re.search(r"AppleWebKit/([0-9.]+)", ua)
    webkit = webkit_match.group(1) if webkit_match else "unknown"
    chrome_match = re.search(r"(?:Chrome|CriOS)/([0-9.]+)", ua)
    chrome = chrome_match.group(1) if chrome_match else "unknown"

    if "iPhone" in ua:
        device = "iPhone"
        os_match = re.search(r"OS ([0-9_]+)", ua)
        os_name = f"iOS {os_match.group(1).replace('_', '.')}" if os_match else "iOS"
        browser_engine = f"AppleWebKit {webkit}" if webkit != "unknown" else "unknown"
    elif "iPad" in ua:
        device = "iPad"
        os_match = re.search(r"OS ([0-9_]+)", ua)
        os_name = f"iPadOS {os_match.group(1).replace('_', '.')}" if os_match else "iPadOS"
        browser_engine = f"AppleWebKit {webkit}" if webkit != "unknown" else "unknown"
    elif "Android" in ua:
        android_match = re.search(r"Android ([^;)\s]+)", ua)
        model_match = re.search(r"Android [^;]+; ([^;)]+)", ua)
        device = model_match.group(1).strip() if model_match else "Android"
        os_name = f"Android {android_match.group(1)}" if android_match else "Android"
        browser_engine = f"Chromium {chrome}" if chrome != "unknown" else "unknown"
    elif "Windows NT" in ua:
        device = "Windows PC"
        os_name = "Windows"
        browser_engine = f"Chromium {chrome}" if chrome != "unknown" else "unknown"
    elif "Macintosh" in ua:
        device = "Mac"
        mac_match = re.search(r"Mac OS X ([0-9_]+)", ua)
        os_name = f"macOS {mac_match.group(1).replace('_', '.')}" if mac_match else "macOS"
        browser_engine = f"AppleWebKit {webkit}" if webkit != "unknown" else "unknown"
    elif "Linux" in ua:
        device = "Linux"
        os_name = "Linux"
        browser_engine = f"Chromium {chrome}" if chrome != "unknown" else "unknown"
    else:
        device = "unknown"
        os_name = "unknown"
        browser_engine = "unknown"

    return device, os_name, browser_engine


def console_client(ip, mac, device, os_name, browser_engine):
    key = (ip, mac, device, os_name, browser_engine)
    if key in SEEN_CLIENTS:
        return
    SEEN_CLIENTS.add(key)
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] CONNECTED "
        f"device={BOLD}{device}{RESET}  ip={ip}  mac={mac}  "
        f"os={os_name}  browser_engine={browser_engine}",
        flush=True,
    )


class WelcomeHandler(http.server.BaseHTTPRequestHandler):
    def log_request_fingerprint(self):
        parsed = urllib.parse.urlsplit(self.path)
        headers = "; ".join(
            f"{clean(name)}={clean(value)}"
            for name, value in self.headers.items()
        ) or "none"
        user_agent = clean(self.headers.get("User-Agent", "unknown"))
        language = clean(self.headers.get("Accept-Language", "unknown"))
        host = clean(self.headers.get("Host", "unknown"))
        lease = lease_for_ip(self.client_address[0])
        device, os_name, browser_engine = user_agent_info(user_agent)
        if device == "unknown" and lease["hostname"] not in ("", "*", "unknown"):
            device = lease["hostname"]
        log_event(
            "WELCOME_REQUEST "
            f"ip={self.client_address[0]}  "
            f"mac={lease['mac']}  "
            f"hostname={lease['hostname']}  "
            f"client_id={lease['client_id']}  "
            f"device={device}  "
            f"os={os_name}  "
            f"browser_engine={browser_engine}  "
            f"method={self.command}  "
            f"path={clean(parsed.path or '/')}  "
            f"query={clean(parsed.query or '-')}  "
            f"host={host}  "
            f"user_agent={user_agent}  "
            f"accept_language={language}  "
            f"headers=\"{headers}\""
        )
        console_client(self.client_address[0], lease["mac"], device, os_name, browser_engine)

    def send_welcome_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(WELCOME_BYTES)))
        self.end_headers()
        self.wfile.write(WELCOME_BYTES)

    def do_GET(self):
        self.log_request_fingerprint()
        self.send_welcome_page()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 0:
            self.rfile.read(length)
        self.log_request_fingerprint()
        self.send_welcome_page()

    def log_message(self, fmt, *args):
        log_event(f"WELCOME_HTTP ip={self.client_address[0]}  message=\"{clean(fmt % args)}\"")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), WelcomeHandler) as httpd:
        print(f"[+] Safety welcome portal on :{PORT}  (AP: {AP_IP})")
        httpd.serve_forever()
