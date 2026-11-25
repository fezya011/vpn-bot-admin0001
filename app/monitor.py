import asyncio
import logging
import time

from aiogram import Bot

from app import system
from app.config import Settings
from app.containers import Docker

log = logging.getLogger("monitor")
BAD = {"exited", "dead", "restarting", "paused"}
COOLDOWN = 1800


async def notify(bot: Bot, admins: list[int], text: str) -> None:
    for uid in admins:
        try:
            await bot.send_message(uid, text)
        except Exception:
            log.warning("cannot notify %s", uid, exc_info=True)


async def monitor_loop(bot: Bot, ops: Docker, s: Settings) -> None:
    prev: dict[str, str] | None = None
    last_alert: dict[str, float] = {}
    while True:
        try:
            alerts: list[str] = []
            items = await asyncio.to_thread(ops.list_containers)
            cur = {c["name"]: ("unhealthy" if c["unhealthy"] else c["status"]) for c in items}
            if prev is not None:
                for name, st in cur.items():
                    old = prev.get(name)
                    if old == st:
                        continue
                    if st in BAD or st == "unhealthy":
                        alerts.append(f"🔴 <b>{name}</b>: {old or 'новый'} → {st}")
                    elif old in BAD or old == "unhealthy":
                        alerts.append(f"🟢 <b>{name}</b> снова работает ({st})")
                for name in prev.keys() - cur.keys():
                    alerts.append(f"🗑 Контейнер <b>{name}</b> исчез")
            prev = cur

            q = await asyncio.to_thread(system.quick)
            now = time.time()
            for key, val, limit, label in (
                ("ram", q["ram_pct"], s.ram_alert_percent, "RAM"),
                ("disk", q["disk_pct"], s.disk_alert_percent, "Диск"),
            ):
                if val >= limit and now - last_alert.get(key, 0) > COOLDOWN:
                    last_alert[key] = now
                    alerts.append(f"🟡 {label}: {val:.0f}% (порог {limit}%)")

            if alerts:
                await notify(bot, s.admin_ids, "🚨 <b>Мониторинг</b>\n\n" + "\n".join(alerts))
        except Exception:
            log.exception("monitor error")
        await asyncio.sleep(s.monitor_interval)
