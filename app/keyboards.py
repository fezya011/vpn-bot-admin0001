from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup as Kb

ICONS = {"running": "🟢", "exited": "🔴", "restarting": "🟡", "paused": "⏸", "dead": "💀"}


def icon(c: dict) -> str:
    return "⚠️" if c.get("unhealthy") else ICONS.get(c["status"], "⚪")


def menu(allow_reboot: bool) -> Kb:
    rows = [
        [Btn(text="📊 Сервер", callback_data="srv"), Btn(text="🐳 Контейнеры", callback_data="ctrs")],
    ]
    if allow_reboot:
        rows.append([Btn(text="⚠️ Перезагрузить сервер", callback_data="hr")])
    return Kb(inline_keyboard=rows)


def refresh(target: str) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🔄 Обновить", callback_data=target), Btn(text="⬅️ Меню", callback_data="menu")],
    ])


def containers(items: list[dict]) -> Kb:
    rows = [[Btn(text=f"{icon(c)} {c['name']}", callback_data=f"c:{c['id']}")] for c in items[:40]]
    rows.append([Btn(text="🔄 Обновить", callback_data="ctrs"), Btn(text="⬅️ Меню", callback_data="menu")])
    return Kb(inline_keyboard=rows)


def detail(cid: str, can_restart: bool) -> Kb:
    first = [Btn(text="📜 Логи", callback_data=f"l:{cid}"), Btn(text="🔄 Обновить", callback_data=f"c:{cid}")]
    rows = [first]
    if can_restart:
        rows.append([Btn(text="♻️ Перезапустить", callback_data=f"r:{cid}")])
    rows.append([Btn(text="⬅️ К списку", callback_data="ctrs")])
    return Kb(inline_keyboard=rows)


def confirm(yes: str, no: str, label: str) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text=label, callback_data=yes)],
        [Btn(text="❌ Отмена", callback_data=no)],
    ])


def logs(cid: str) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🔄 Обновить", callback_data=f"l:{cid}"), Btn(text="⬅️ Назад", callback_data=f"c:{cid}")],
    ])
