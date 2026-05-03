#!/usr/bin/env python3

"""Safety-focused captive portal web server for JmilAP hotspot.
Usage: python3 welcome.py [ap_ip]   (default: 192.168.50.1)
"""

import http.server
import os
import re
import socketserver
import sys
import urllib.parse
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(_HERE, "image.jpg")

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
    <title>WARNING</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        html {{ background: #000; }}

        body {{
            background: #000;
            color: #00ff41;
            font-family: "Courier New", Courier, monospace;
        }}

        /* global CRT scan lines */
        body::before {{
            content: "";
            position: fixed;
            inset: 0;
            background: repeating-linear-gradient(
                0deg,
                rgba(0,0,0,.13) 0px,
                rgba(0,0,0,.13) 1px,
                transparent 1px,
                transparent 3px
            );
            pointer-events: none;
            z-index: 1000;
        }}

        /* ── HERO ── */
        .hero {{
            position: relative;
            width: 100%;
            height: 100vh;
            overflow: hidden;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            padding-bottom: 60px;
        }}

        .hero-img {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center 18%;
            filter: grayscale(38%) contrast(1.14) brightness(0.66);
            animation: img-glitch 12s infinite;
        }}

        /* dense scan lines on image */
        .hero::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(
                0deg,
                rgba(0,0,0,.28) 0px,
                rgba(0,0,0,.28) 1px,
                transparent 1px,
                transparent 4px
            );
            z-index: 2;
            pointer-events: none;
        }}

        /* vignette + bottom fade to black */
        .hero::after {{
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(ellipse at center, transparent 32%, rgba(0,0,0,.88) 100%),
                linear-gradient(180deg, rgba(0,0,0,.45) 0%, transparent 25%, transparent 55%, rgba(0,0,0,.95) 100%);
            z-index: 3;
            pointer-events: none;
        }}

        /* glitch color bar */
        .glitch-bar {{
            position: absolute;
            inset: 0;
            clip-path: inset(0 0 100% 0);
            pointer-events: none;
            z-index: 4;
            animation: bar-glitch 12s step-start infinite;
        }}

        .tagline {{
            position: relative;
            z-index: 5;
            font-size: clamp(20px, 3.5vw, 38px);
            font-weight: 400;
            letter-spacing: .22em;
            text-transform: lowercase;
            color: #00ff41;
            text-shadow:
                0 0 12px rgba(0,255,65,.95),
                0 0 36px rgba(0,255,65,.45),
                0 0 80px rgba(0,255,65,.18);
            animation: tag-pulse 3.5s ease-in-out infinite;
        }}

        /* ── TERMINAL ── */
        .terminal {{
            max-width: 660px;
            margin: 0 auto;
            padding: 72px 28px 88px;
        }}

        .dim {{ color: rgba(0,255,65,.38); font-size: clamp(12px,1.8vw,14px); line-height: 2.1; }}
        .dim::before {{ content: "> "; }}

        .gap {{ height: 26px; }}

        h1 {{
            font-size: clamp(36px,7vw,68px);
            font-weight: 400;
            line-height: 1.06;
            color: #00ff41;
            text-shadow: 0 0 22px rgba(0,255,65,.55), 0 0 60px rgba(0,255,65,.18);
        }}
        h1 .no {{
            display: block;
            color: #ff3c00;
            text-shadow: 0 0 18px rgba(255,60,0,.8), 0 0 50px rgba(255,60,0,.25);
        }}

        .rule {{ border: none; border-top: 1px solid rgba(0,255,65,.18); margin: 28px 0; }}

        .warn-list {{ list-style: none; display: flex; flex-direction: column; gap: 12px; }}
        .warn-list li {{ font-size: clamp(13px,2vw,16px); line-height: 1.5; }}
        .warn-list li::before {{ content: "[!] "; color: #ff3c00; text-shadow: 0 0 8px rgba(255,60,0,.9); }}

        .footer {{ margin-top: 36px; font-size: clamp(11px,1.6vw,13px); color: rgba(0,255,65,.3); letter-spacing: .05em; }}

        .cursor {{
            display: inline-block;
            width: 9px; height: .9em;
            background: #00ff41;
            vertical-align: text-bottom;
            margin-left: 3px;
            box-shadow: 0 0 8px rgba(0,255,65,.8);
            animation: blink 1.1s step-end infinite;
        }}

        /* ── ANIMATIONS ── */
        @keyframes blink {{
            0%,100% {{ opacity: 1; }}
            50% {{ opacity: 0; }}
        }}

        @keyframes tag-pulse {{
            0%,100% {{
                text-shadow: 0 0 12px rgba(0,255,65,.95), 0 0 36px rgba(0,255,65,.45), 0 0 80px rgba(0,255,65,.18);
            }}
            50% {{
                text-shadow: 0 0 18px rgba(0,255,65,1), 0 0 52px rgba(0,255,65,.6), 0 0 110px rgba(0,255,65,.25);
            }}
        }}

        @keyframes img-glitch {{
            0%, 86%, 100% {{
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }}
            87% {{
                transform: translate(-6px, 2px);
                filter: grayscale(75%) contrast(1.45) brightness(0.52) hue-rotate(85deg);
            }}
            87.6% {{
                transform: translate(6px, -2px);
                filter: grayscale(15%) contrast(1.05) brightness(0.88) saturate(2);
            }}
            88.2% {{
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }}
            93% {{
                transform: translate(4px, 1px);
                filter: grayscale(95%) contrast(1.6) brightness(0.5);
            }}
            93.6% {{
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }}
        }}

        @keyframes bar-glitch {{
            0%, 86%, 100% {{ clip-path: inset(0 0 100% 0); background: transparent; }}
            87%   {{ clip-path: inset(12% 0 75% 0); background: rgba(0,255,65,.1); }}
            87.3% {{ clip-path: inset(52% 0 36% 0); background: rgba(255,60,0,.12); }}
            87.6% {{ clip-path: inset(0 0 100% 0); background: transparent; }}
            93%   {{ clip-path: inset(28% 0 64% 0); background: rgba(0,255,65,.08); }}
            93.4% {{ clip-path: inset(0 0 100% 0); background: transparent; }}
        }}
    </style>
</head>
<body>
    <section class="hero" aria-label="Warning — they are watching">
        <img class="hero-img" src="/image.jpg" alt="anonymous mask">
        <div class="glitch-bar" aria-hidden="true"></div>
        <p class="tagline">they are watching.</p>
    </section>

    <section class="terminal" aria-label="Security warning">
        <p class="dim">scanning traffic&hellip;</p>
        <p class="dim">hello, friend.</p>
        <div class="gap"></div>
        <h1>
            FREE WIFI
            <span class="no">&#x2260;&nbsp;SAFE WIFI</span>
        </h1>
        <hr class="rule">
        <ul class="warn-list" aria-label="Security warnings">
            <li>captive portals can steal your credentials</li>
            <li>your traffic is visible to the AP owner</li>
            <li>never log in on a network you don&#x27;t own</li>
        </ul>
        <p class="footer">stay dark. stay safe.<span class="cursor" aria-hidden="true"></span></p>
    </section>
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
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(WELCOME_BYTES)

    def send_image(self):
        try:
            image_size = os.path.getsize(IMAGE_PATH)
            image_file = open(IMAGE_PATH, "rb")
        except OSError:
            self.send_error(404)
            return

        with image_file:
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(image_size))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            while True:
                chunk = image_file.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def should_serve_image(self):
        parsed = urllib.parse.urlsplit(self.path)
        return parsed.path == "/image.jpg"

    def do_GET(self):
        self.log_request_fingerprint()
        if self.should_serve_image():
            self.send_image()
            return
        self.send_welcome_page()

    def do_HEAD(self):
        self.log_request_fingerprint()
        if self.should_serve_image():
            try:
                image_size = os.path.getsize(IMAGE_PATH)
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(image_size))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(WELCOME_BYTES)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

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
