import os
import time

import psutil

GB = 1024**3


def snapshot() -> dict:
    vm, sw, du = psutil.virtual_memory(), psutil.swap_memory(), psutil.disk_usage("/")
    return {
        "cpu": psutil.cpu_percent(interval=0.5),
        "cores": psutil.cpu_count() or 1,
        "load": os.getloadavg(),
        "ram_used": vm.total - vm.available,
        "ram_total": vm.total,
        "ram_pct": vm.percent,
        "swap_used": sw.used,
        "swap_total": sw.total,
        "disk_used": du.used,
        "disk_total": du.total,
        "disk_pct": du.percent,
        "uptime": time.time() - psutil.boot_time(),
    }


def quick() -> dict:
    return {"ram_pct": psutil.virtual_memory().percent, "disk_pct": psutil.disk_usage("/").percent}


def uptime(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    return (f"{d}д " if d else "") + f"{h}ч {m}м"


def _mark(pct: float) -> str:
    return "🔴" if pct >= 90 else "🟡" if pct >= 75 else "🟢"


def format_snapshot(s: dict) -> str:
    l1, l5, l15 = s["load"]
    swap = (
        f"{s['swap_used'] / GB:.2f}/{s['swap_total'] / GB:.2f} ГБ" if s["swap_total"] else "нет"
    )
    return (
        "🖥 <b>Сервер</b>\n\n"
        f"{_mark(s['cpu'])} CPU: {s['cpu']:.0f}% ({s['cores']} яд.)\n"
        f"   load: {l1:.2f} / {l5:.2f} / {l15:.2f}\n"
        f"{_mark(s['ram_pct'])} RAM: {s['ram_used'] / GB:.2f}/{s['ram_total'] / GB:.2f} ГБ "
        f"({s['ram_pct']:.0f}%)\n"
        f"   swap: {swap}\n"
        f"{_mark(s['disk_pct'])} Диск /: {s['disk_used'] / GB:.1f}/{s['disk_total'] / GB:.1f} ГБ "
        f"({s['disk_pct']:.0f}%)\n"
        f"⏱ Аптайм: {uptime(s['uptime'])}"
    )
