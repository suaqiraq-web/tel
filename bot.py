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
    "الكل — عرض قائمة كل المشتركين والإحصائيات\n"
    "بحث اسم — البحث عن مشترك برابطه/يوزره\n"
    "اضف اسم عدد-الأيام — إضافة مشترك جديد\n"
    "تعديل اسم عدد-الأيام — تعديل مدة الاشتراك\n"
    "وقف اسم — إيقاف اشتراك مشترك\n"
    "تفعيل اسم — إعادة تفعيل المشترك\n"
    "ربط اسم ip — ربط عنوان IP بمشترك\n"
    "معلومات اسم — عرض تفاصيل مشترك معين\n"
    "حذف اسم — حذف المشترك نهائياً")


def load():
    try:
        os.makedirs(os.path.dirname(DATA), exist_ok=True)
        with open(DATA) as f:
            return json.load(f)
    except Exception:
        return {"subscribers": {}, "free_used": []}


def save(db):
    folder = os.path.dirname(DATA)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
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

    if cmd in ("start", "help", "menu", "الاوامر", "الأوامر", "تعليمات"):
        send(chat_id, OWNER_HELP)
        return

    # عرض جميع المشتركين والإحصائيات الكلية
    if cmd in ("الكل", "all"):
        subs = db.get("subscribers", {})
        free_used = db.get("free_used", [])
        
        active_cnt = sum(1 for s in subs.values() if s.get("active", True))
        stopped_cnt = len(subs) - active_cnt
        total_free = len(free_used)
        
        header = (
            "📊 **إحصائيات البوت:**\n"
            "• إجمالي المشتركين الحاليين: %d\n"
            "• المفعلين: %d | الموقوفين: %d\n"
            "• مستخدمي التجربة المجانية الكلي: %d\n\n"
            "📋 **قائمة المشتركين:**\n"
        ) % (len(subs), active_cnt, stopped_cnt, total_free)

        if not subs:
            send(chat_id, header + "لا يوجد مشتركين مسجلين بعد.")
            return

        lines = []
        for name, s in subs.items():
            st = "\U0001F7E2" if s.get("active", True) else "\U0001F534"
            exp = s.get("expiry", "-")
            lines.append("%s %s — حتى %s" % (st, name, exp))
        
        send(chat_id, header + "\n".join(lines))
        return

    # البحث عن اسم مشترك أو يوزر
    if cmd in ("بحث", "search"):
        if not args:
            send(chat_id, "يرجى كتابة الاسم للبحث. مثال: بحث علي")
            return
        query = args[0].lstrip("@").lower()
        subs = db.get("subscribers", {})
        results = [name for name in subs if query in name.lower()]
        
        if not results:
            send(chat_id, "لم يتم العثور على أي مشترك يحتوي على: " + query)
            return
            
        lines = []
        for name in results:
            s = subs[name]
            st = "\U0001F7E2" if s.get("active", True) else "\U0001F534"
            lines.append("%s %s — ينتهي: %s" % (st, name, s.get("expiry", "-")))
            
        send(chat_id, "🔎 نتائج البحث (%d):\n\n%s" % (len(results), "\n".join(lines)))
        return

    # إضافة تعديل أو مشترك جديد
    if cmd in ("اضف", "أضف", "add", "تعديل", "plan"):
        if len(args) < 1:
            send(chat_id, "استخدام: اضف اسم [عدد الأيام]")
            return
        name = args[0].lstrip("@")
        days = parse_days(args[1]) if len(args) > 1 else 2
        if days is None:
            send(chat_id, "المدة غير صحيحة.")
            return
        subs = db.setdefault("subscribers", {})
        if cmd in ("اضف", "أضف", "add"):
            if name in subs:
                send(chat_id, "الاسم مسجل مسبقاً. استخدم أمر (معلومات اسم) للتفاصيل.")
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
            send(chat_id, "تم التسجيل بنجاح:\n\n" + fmt_sub(name, sub))
        else:
            sub = subs.get(name)
            if not sub:
                send(chat_id, "هذا المشترك غير مسجل.")
                return
            sub["plan"] = "%dd" % days
            sub["expiry"] = expiry_str(days)
            save(db)
            send(chat_id, "تم تعديل مدة %s — تنتهي %s" % (name, sub["expiry"]))
        return

    # التحكم المباشر بالعربي
    if cmd in ("وقف", "تفعيل", "ربط", "معلومات", "حذف", "stop", "on", "ip", "info", "del"):
        if not args:
            send(chat_id, "استخدام: %s اسم" % cmd)
            return
        name = args[0].lstrip("@")
        subs = db.get("subscribers", {})
        sub = subs.get(name)
        if not sub:
            send(chat_id, "الاسم %s غير مسجل." % name)
            return
            
        if cmd in ("وقف", "stop"):
            sub["active"] = False
            save(db)
            send(chat_id, "تم إيقاف %s — سيتم قطع اتصاله." % name)
        elif cmd in ("تفعيل", "on"):
            sub["active"] = True
            save(db)
            send(chat_id, "تم تفعيل %s." % name)
        elif cmd in ("ربط", "ip"):
            ip = args[1] if len(args) > 1 else ""
            if ip and not re.match(r"^[0-9a-fA-F:.]{3,45}$", ip):
                send(chat_id, "عنوان IP غير صحيح.")
                return
            sub["ip"] = ip
            save(db)
            send(chat_id, "تم ربط %s بالـ IP: %s" % (name, ip if ip else "— (مسح الربط)"))
        elif cmd in ("معلومات", "info"):
            send(chat_id, fmt_sub(name, sub))
        elif cmd in ("حذف", "del"):
            del subs[name]
            save(db)
            send(chat_id, "تم حذف %s نهائياً." % name)
        return


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
                send(chat_id, "أنت المالك! اكتب (الاوامر) لرؤية قائمة التحكم.")
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
        send(chat_id, "تهانينا! أنت الآن المالك. اكتب (الاوامر) لفتح اللوحة.")
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
