import os
import json


def load_subs():
    try:
        with open("/data/subs.json") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    subs = load_subs()
    dat = subs.get("subscribers", {})

    users = {}
    exp = {}
    ips = {}
    conns = {"admin": 32}

    for name, s in dat.items():
        if not isinstance(s, dict):
            continue
        secret = str(s.get("secret", ""))
        if len(secret) != 32:
            continue
        if not bool(s.get("active", True)):
            continue
        users[name] = secret
        if s.get("expiry"):
            exp[name] = str(s["expiry"])
        if s.get("ip"):
            ips[name] = str(s["ip"])
        conns[name] = 4

    admin = os.environ.get("SECRET", "c7b105c8829e465a542b58d61d1d235f")
    users["admin"] = admin

    port = int(os.environ.get("PORT", "443"))

    cfg = """PORT = %d

USERS = %s

USER_EXPIRATIONS = %s

USER_ALLOWED_IPS = %s

USER_MAX_TCP_CONNS = %s

MODES = {
    "classic": False,
    "secure": False,
    "tls": True,
}

FAST_MODE = True
PREFER_IPV6 = False

TO_CLT_BUFSIZE = 1048576
TO_TG_BUFSIZE = 1048576

TG_CONNECT_TIMEOUT = 100
TG_READ_TIMEOUT = 100
CLIENT_HANDSHAKE_TIMEOUT = 100
""" % (
        port,
        json.dumps(users, indent=4),
        json.dumps(exp, indent=4),
        json.dumps(ips, indent=4),
        json.dumps(conns, indent=4),
    )

    with open("config.py", "w") as f:
        f.write(cfg)

    print("config.py regenerated: %d subscribers, %d active" % (len(dat), len(users) - 1))


if __name__ == "__main__":
    main()