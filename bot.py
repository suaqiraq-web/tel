import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

TOKEN = os.environ.get("BOT_TOKEN", "")
PUBLIC_IP = os.environ.get("PUBLIC_IP", "")
PORT = os.environ.get("PORT", "443")
EXT_PORT = os.environ.get("EXTERNAL_PORT", PORT)
ADMIN_TG_ID = os.environ.get("ADMIN_TG_ID", "")
CONTACT = os.environ.get("SUBSCRIBE_CONTACT", "@fadl22b")
PRICE = os.environ.get("PRICE_MONTHLY", "1500 دينار عراقي")
API = "https://api.telegram.org/bot%s" % TOKEN
DATA = "/data/subs.json"
TLS_DOMAIN_HEX = "7777772e676f6f676c652e636f6d"

OWNER_HELP = ("أوامر التحكم (خاصة بالمالك)\n\n"
    "/all — كل المشتركين\n"
    "/add اسم عدد-الأيام — مشترك جديد\n"
    "/plan اسم عدد-الأيام — تعديل المدة\n"
    "/stop اسم — إيقاف\n"
    "/on اسم — تفعيل\n"
    "/ip اسم ip — ربط IP\n"
    "/info اسم — التفاصيل\n"
    "/del اسم — حذف نهائي")


def load():
    try:
        with open(DATA) as f:
            return json.load(f)
    except Exception:
        return {"subscribers": {}, "free_used": []}


def save(db):
    tmp = DATA + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA)


def api(method, **params):
    url = API + "/" + method
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read())


def send(chat_id, text, markup=None):
    try:
        params = {"chat_id": chat_id, "text": text}
        if markup:
            params["reply_markup"] = json.dumps(markup)
        api("sendMessage", **params)
    except Exception:
        pass


def get_updates(offset):
    try:
        return api("getUpdates", offset=offset, timeout=30)["result"]
    except Exception:
        return []


def proxy_link(secret):
    return "tg://proxy?server=%s&port=%s&secret=ee%s%s" % (PUBLIC_IP, EXT_PORT, secret, TLS_DOMAIN_HEX)


def expiry_str(days):
    return (date.today() + timedelta(days=days)).strftime("%d/%m/%Y")


def parse_days(text):
    m = re.match(r"^(\d+)\s*([dwmy])?$", str(text).strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2) or "d"
    if unit == "d":
        return n
    if unit == "w":
        return n * 7
    if unit == "m":
        return n * 30
    return n * 365


def is_owner(chat_id, db):
    if ADMIN_TG_ID and str(chat_id) == str(ADMIN_TG_ID):
        return True
    return db.get("admin_id") == chat_id


def public_menu():
    return ("🔥 بروكسي سريع للتلكرام\n\n"
        "💎 الاشتراك الشهري: %s\n"
        "🎁 يومين مجانية تجربة، مرة وحدة فقط لكل حساب\n\n"
        "للاستشارة والاشتراك تواصل مع المطور:\n%s\n\n"
        "اضغط الزر واجرب يومين مجانية") % (PRICE, CONTACT)


def fmt_sub(name, s):
    status = "\U0001F7E2 مفعل" if s.get("active", True) else "\U0001F534 موقوف"
    lines = ["الاسم: %s" % name,
             "الحالة: %s" % status,
             "ينتهي: %s" % s.get("expiry", "-"),
             "IP: %s" % s.get("ip", "غير مربوط")]
    if s.get("secret"):
        lines.append("")
        lines.append("لينك البروكسي:")
        lines.append(proxy_link(s["secret"]))
    return "\n".join(lines)


def grant_trial(chat_id, user_from):
    uid = user_from.get("id")
    db = load()
    free_used = db.setdefault("free_used", [])
    if uid in free_used:
        send(chat_id, "لقد استعملت الفترة المجانية سابقًا، وما تكدر تكررها. للاشتراك تواصل مع المطور:\n%s" % CONTACT)
        return
    username = user_from.get("username")
    name = ("trial_" + username) if username else ("trial_user" + str(uid))
    subs = db.setdefault("subscribers", {})
    if name in subs:
        name = name + "_" + str(int(time.time()))
    sub = {
        "secret": secrets.token_hex(16),
        "plan": "2d مجانية",
        "expiry": expiry_str(2),
        "ip": "",
        "active": True,
        "created": expiry_str(0),
        "trial": True,
        "tg_id": uid,
    }
    subs[name] = sub
    free_used.append(uid)
    save(db)
    text = ("🎁 مبروك! يومين مجانية لك\n\n"
        "اللينك:\n%s\n\n"
        "ينتهي: %s\n\n"
        "💎 الاشتراك الشهري: %s\n"
        "للاستشارة والتثبيت بشكل دائم تواصل مع المطور:\n%s") % (proxy_link(sub["secret"]), sub["expiry"], PRICE, CONTACT)
    send(chat_id, text)


def owner_handle(chat_id, text):
    parts = text.split()
    cmd = parts[0].strip("/").lower()
    args = parts[1:]
    db = load()

    if cmd in ("start", "help", "menu"):
        send(chat_id, OWNER_HELP)
        return

    if cmd == "all":
        subs = db.get("subscribers", {})
        if not subs:
            send(chat_id, "لا يوجد مشتركين.")
            return
        lines = []
        for name, s in subs.items():
            st = "\U0001F7E2" if s.get("active", True) else "\U0001F534"
            exp = s.get("expiry", "-")
            lines.append("%s %s — حتى %s" % (st, name, exp))
        send(chat_id, "المشتركين (%d):\n\n%s" % (len(subs), "\n".join(lines)))
        return

    if cmd in ("add", "plan"):
        if len(args) < 1:
            send(chat_id, "استخدام: /%s اسم [عدد الأيام]" % cmd)
            return
        name = args[0].lstrip("@")
        days = parse_days(args[1]) if len(args) > 1 else 2
        if days is None:
            send(chat_id, "المدة غير صحيحة.")
            return
        subs = db.setdefault("subscribers", {})
        if cmd == "add":
            if name in subs:
                send(chat_id, "الاسم مسجل مسبقًا. استخدم /info لمنظر التفاصيل.")
                return
            sub = {
                "secret": secrets.token_hex(16),
                "plan": "%dd" % days,
                "expiry": expiry_str(days),
                "ip": "",
                "active": True,
                "created": expiry_str(0),
            }
            subs[name] = sub
            save(db)
            send(chat_id, "تم التسجيل:\n\n" + fmt_sub(name, sub))
        else:
            sub = subs.get(name)
            if not sub:
                send(chat_id, "غير مسجل.")
                return
            sub["plan"] = "%dd" % days
            sub["expiry"] = expiry_str(days)
            save(db)
            send(chat_id, "تم تعديل مدة %s — تنتهي %s" % (name, sub["expiry"]))
        return

    if cmd in ("stop", "on", "ip", "info", "del"):
        if not args:
            send(chat_id, "استخدام: /%s اسم ..." % cmd)
            return
        name = args[0].lstrip("@")
        subs = db.get("subscribers", {})
        sub = subs.get(name)
        if not sub:
            send(chat_id, "الاسم %s غير مسجل." % name)
            return
        if cmd == "stop":
            sub["active"] = False
            save(db)
            send(chat_id, "تم إيقاف %s — بعد دقيقة يقطع اتصاله." % name)
        elif cmd == "on":
            sub["active"] = True
            save(db)
            send(chat_id, "تم تفعيل %s." % name)
        elif cmd == "ip":
            ip = args[1] if len(args) > 1 else ""
            if ip and not re.match(r"^[0-9a-fA-F:.]{3,45}$", ip):
                send(chat_id, "IP غير صحيح.")
                return
            sub["ip"] = ip
            save(db)
            send(chat_id, "تم ربط %s بالـ IP: %s" % (name, ip if ip else "— (مسح الربط)"))
        elif cmd == "info":
            send(chat_id, fmt_sub(name, sub))
        elif cmd == "del":
            del subs[name]
            save(db)
            send(chat_id, "تم حذف %s نهائيًا." % name)
        return

    send(chat_id, "أمر غير معروف. اكتب /help")


def user_handle(chat_id, text, user_from):
    word = re.sub(r"[^\w]", "", text.replace("\u064b", "").replace("\u064c", "")
                  .replace("\u064d", "").replace("\u064e", "").replace("\u064f", "")
                  .replace("\u0650", "").replace("\u0651", "").replace("\u0652", "").lower())
    if "مجان" in word or word in ("trial", "free", "تجربة"):
        grant_trial(chat_id, user_from)
        return
    markup = {"inline_keyboard": [[{"text": "🔥 جرب يومين مجانية", "callback_data": "trial"}]]}
    send(chat_id, public_menu(), markup=markup)


def handle(update):
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        user_from = cb.get("from", {})
        if cb.get("data") == "trial" and chat_id:
            db = load()
            if not is_owner(chat_id, db):
                grant_trial(chat_id, user_from)
            else:
                send(chat_id, "أنت المالك، عندك صلاحية دائمة 😉")
        return

    msg = update.get("message")
    if not msg:
        return
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    user_from = msg.get("from", {})
    if not text:
        return

    db = load()
    if db.get("admin_id") is None and not ADMIN_TG_ID:
        db["admin_id"] = chat_id
        save(db)
        send(chat_id, "تهانينا! أنت الآن المالك. اكتب /help للأوامر.")
        return

    if is_owner(chat_id, db):
        owner_handle(chat_id, text)
    else:
        user_handle(chat_id, text, user_from)


def main():
    offset = 0
    while True:
        for update in get_updates(offset):
            offset = update["update_id"] + 1
            handle(update)
        time.sleep(1)


if __name__ == "__main__":
    main()