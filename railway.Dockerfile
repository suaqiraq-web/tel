FROM python:3.11-alpine

RUN apk add --no-cache git gcc musl-dev libffi-dev build-base

RUN git clone https://github.com/alexbers/mtprotoproxy.git /app

WORKDIR /app

RUN pip install --no-cache-dir cryptography uvloop

RUN sed -i 's/MAX_CONNS_IN_POOL = 16/MAX_CONNS_IN_POOL = 64/' mtprotoproxy.py

RUN python3 - <<'PYEOF'
path = "mtprotoproxy.py"
src = open(path).read()

# 1) per-user IP allowlist check
old_ip = """        reader = CryptoWrappedStreamReader(reader, decryptor)
        writer = CryptoWrappedStreamWriter(writer, encryptor)
        return reader, writer, proto_tag, user, dc_idx, enc_key + enc_iv, peer"""
new_ip = """        reader = CryptoWrappedStreamReader(reader, decryptor)
        writer = CryptoWrappedStreamWriter(writer, encryptor)
        if user in getattr(config, "USER_ALLOWED_IPS", {}):
            if peer[0] not in config.USER_ALLOWED_IPS[user]:
                print_err("IP %s is not allowed for user %s" % (peer[0], user))
                await handle_bad_client(reader, writer, handshake)
                return False
        return reader, writer, proto_tag, user, dc_idx, enc_key + enc_iv, peer"""
assert old_ip in src, "ip anchor not found"
src = src.replace(old_ip, new_ip)

# 2) dynamic config watcher function
old_main = """def main():
    init_config()"""
new_main = """async def watch_dynamic_config():
    import subprocess
    path = "/data/subs.json"
    last_mtime = 0.0
    try:
        last_mtime = os.path.getmtime(path)
    except OSError:
        pass
    while True:
        await asyncio.sleep(3)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime == last_mtime:
            continue
        last_mtime = mtime
        try:
            res = subprocess.run(["python3", "/app/genconfig.py"], capture_output=True, timeout=20)
            if res.returncode == 0:
                init_config()
                ensure_users_in_user_stats()
                apply_upstream_proxy_settings()
                print("Dynamic subscribers config reloaded", flush=True, file=sys.stderr)
                print_tg_info()
            else:
                err = res.stderr.decode(errors="replace")
                print("genconfig failed: %s" % err[:500], flush=True, file=sys.stderr)
        except Exception as E:
            print("config reload error: %s" % E, flush=True, file=sys.stderr)


def main():
    init_config()"""
assert old_main in src, "main anchor not found"
src = src.replace(old_main, new_main)

# 3) register the watcher task
old_task = """    clear_resolving_cache_task = asyncio.Task(clear_ip_resolving_cache(), loop=loop)
    tasks.append(clear_resolving_cache_task)

    return tasks"""
new_task = """    clear_resolving_cache_task = asyncio.Task(clear_ip_resolving_cache(), loop=loop)
    tasks.append(clear_resolving_cache_task)

    dynamic_config_task = asyncio.Task(watch_dynamic_config(), loop=loop)
    tasks.append(dynamic_config_task)

    return tasks"""
assert old_task in src, "task anchor not found"
src = src.replace(old_task, new_task)

open(path, "w").write(src)
print("patched")
PYEOF

COPY genconfig.py /app/genconfig.py
COPY bot.py /app/bot.py
COPY railway/run.sh /app/run.sh

RUN chmod +x /app/run.sh

ENV PORT=443
EXPOSE 443
VOLUME /data

CMD ["sh", "/app/run.sh"]