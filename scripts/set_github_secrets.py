"""Write repo secrets via GitHub API (reads PAT + values from local files, never prints them)."""
import base64
import json
import os
import urllib.request

from nacl import encoding as nacl_enc
from nacl import public as nacl_public

OWNER, REPO = "0xSatwik", "peter-video-maker-github"


def load_env(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def api(pat, method, path, data=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        data=json.dumps(data).encode() if data is not None else None,
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read() or b"{}")


def main():
    home = os.path.expanduser("~")
    env = load_env(os.path.join(home, ".peter-deploy", "deploy.env"))
    with open(os.path.join(home, ".kaggle", "kaggle.json"), encoding="utf-8") as f:
        kcreds = json.load(f)
    secrets = {
        "KAGGLE_USERNAME": kcreds["username"],
        "KAGGLE_KEY": kcreds["key"],
        "CALLBACK_URL": "https://peter-video-maker.pages.dev/api/complete",
        "CALLBACK_SECRET": env["CALLBACK_SECRET"],
    }
    _, pub = api(env["GH_PAT"], "GET", "/actions/secrets/public-key")
    pk = nacl_public.PublicKey(pub["key"], nacl_enc.Base64Encoder())
    for name, val in secrets.items():
        enc = nacl_public.SealedBox(pk).encrypt(val.encode())
        st, _ = api(
            env["GH_PAT"],
            "PUT",
            f"/actions/secrets/{name}",
            {
                "encrypted_value": base64.b64encode(bytes(enc)).decode(),
                "key_id": pub["key_id"],
            },
        )
        print(name, st)


if __name__ == "__main__":
    main()
