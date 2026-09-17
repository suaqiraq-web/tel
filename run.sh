#!/bin/sh
set -e

export PORT=443

mkdir -p /data
if [ ! -f /data/subs.json ]; then
    echo '{"admin_id": null, "subscribers": {}, "free_used": []}' > /data/subs.json
fi

python3 /app/genconfig.py

python3 /app/bot.py &

exec python3 /app/mtprotoproxy.py