"""Upload the finished video to a temporary file host and print the public URL.

Two hosts, no splitting and no multipart:
  1. sto.care (ul.sto.care) - single PUT, direct download link, 100 MB max, 72 h
  2. gofile.io               - single POST, unlimited size, download page, ~10 days

Usage:
    python scripts/upload_temp.py output/final_reel.mp4
Prints the share URL on the last line (and to stdout for command substitution).
"""
import os
import sys
import time

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
STO_MAX = 100 * 1024 * 1024  # sto.care API hard limit


def upload_stocare(path, size):
    """Single PUT -> {"url": ..., "expiresAt": ...}"""
    name = os.path.basename(path)
    url = "https://ul.sto.care/" + name
    with open(path, "rb") as f:
        r = requests.put(
            url,
            data=f,
            headers={
                "User-Agent": UA,
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
            },
            timeout=900,
        )
    print(f"sto.care -> HTTP {r.status_code}")
    if r.status_code == 200:
        try:
            return r.json().get("url")
        except ValueError:
            txt = r.text.strip()
            return txt if txt.startswith("http") else None
    print("sto.care body:", r.text[:300])
    return None


def upload_gofile(path):
    """Pick a server, then POST the file."""
    s = requests.get("https://api.gofile.io/servers", headers={"User-Agent": UA}, timeout=60).json()
    servers = (s.get("data") or {}).get("servers") or []
    if not servers:
        print("gofile: no servers ->", str(s)[:200])
        return None
    server = servers[0].get("name")
    with open(path, "rb") as f:
        r = requests.post(
            f"https://{server}.gofile.io/contents/uploadfile",
            files={"file": (os.path.basename(path), f, "video/mp4")},
            headers={"User-Agent": UA},
            timeout=1800,
        )
    print(f"gofile -> HTTP {r.status_code}")
    try:
        data = r.json().get("data") or {}
    except ValueError:
        print("gofile body:", r.text[:300])
        return None
    return data.get("downloadPage") or data.get("directLink")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "output/final_reel.mp4"
    if not os.path.exists(path):
        print("FATAL: file not found:", path)
        sys.exit(1)
    size = os.path.getsize(path)
    print(f"uploading {path} ({size / 1048576:.1f} MB)")

    url = None
    if size <= STO_MAX:
        for attempt in range(2):
            try:
                url = upload_stocare(path, size)
            except Exception as e:  # noqa: BLE001
                print("sto.care exception:", e)
            if url:
                break
            time.sleep(3)

    if not url:
        print("falling back to gofile")
        try:
            url = upload_gofile(path)
        except Exception as e:  # noqa: BLE001
            print("gofile exception:", e)

    if not url:
        print("FATAL: all temp hosts failed")
        sys.exit(1)

    print("TEMP_URL=" + url)
    print(url)


if __name__ == "__main__":
    main()
