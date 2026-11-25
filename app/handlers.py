import asyncio
import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from docker.errors import DockerException, NotFound

from app import keyboards as kb
from app import system
from app.containers import Docker

router = Router()
log = logging.getLogger("admin")
MENU = "🛠 <b>Админ-панель</b>"


async def edit(c: CallbackQuery, text: str, markup=None) -> None:
    try:
        await c.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise


def _gb(b: int | None) -> str:
    return f"{b / 1024**3:.2f} ГБ" if b is not None else "—"


def _mb(b: int | None) -> str:
    return f"{b / 1024**2:.0f} МБ" if b is not None else "—"


def containers_text(items: list[dict]) -> str:
    if not items:
        return "🐳 Контейнеров нет"
    lines = [f"{kb.icon(c)} <code>{html.escape(c['name'])}</code> — {c['status']}" for c in items]
    return "🐳 <b>Контейнеры</b>\n\n" + "\n".join(lines)


def detail_text(i: dict) -> str:
    lines = [
        f"🐳 <b>{html.escape(i['name'])}</b>",
        f"Статус: {i['status']}" + (f" ({i['health']})" if i["health"] else ""),
        f"Образ: <code>{html.escape(i['image'])}</code>",
        f"Рестартов (авто): {i['restarts']}",
    ]
    if i["uptime"]:
        lines.append(f"Аптайм: {i['uptime']}")
    if i["cpu"] is not None:
        lines.append(f"CPU: {i['cpu']:.1f}%")
        limit = i["mem_limit"]
        lines.append(f"RAM: {_mb(i['mem'])}" + (f" / {_gb(limit)}" if limit else ""))
    if i["status"] == "exited":
        lines.append(f"Код выхода: {i['exit_code']}")
    return "\n".join(lines)


@router.message(CommandStart())
@router.message(Command("menu"))
async def menu_cmd(m: Message, settings):
    await m.answer(MENU, reply_markup=kb.menu(settings.allow_host_reboot))


@router.callback_query(F.data == "menu")
async def menu_cb(c: CallbackQuery, settings):
    await edit(c, MENU, kb.menu(settings.allow_host_reboot))
    await c.answer()


@router.message(Command("status"))
async def status_cmd(m: Message):
    snap = await asyncio.to_thread(system.snapshot)
    await m.answer(system.format_snapshot(snap), reply_markup=kb.refresh("srv"))


@router.callback_query(F.data == "srv")
async def server(c: CallbackQuery):
    await c.answer()
    snap = await asyncio.to_thread(system.snapshot)
    await edit(c, system.format_snapshot(snap), kb.refresh("srv"))


@router.callback_query(F.data == "ctrs")
async def containers(c: CallbackQuery, ops: Docker):
    try:
        items = await asyncio.to_thread(ops.list_containers)
    except DockerException:
        log.exception("docker unavailable")
        return await c.answer("Docker недоступен", show_alert=True)
    await edit(c, containers_text(items), kb.containers(items))
    await c.answer()


async def show_detail(c: CallbackQuery, ops: Docker, cid: str) -> None:
    try:
        info = await asyncio.to_thread(ops.detail, cid)
    except NotFound:
        return await edit(c, "Контейнер не найден (мог быть пересоздан).", kb.refresh("ctrs"))
    except DockerException:
        log.exception("detail failed")
        return await edit(c, "⚠️ Docker вернул ошибку.", kb.refresh("ctrs"))
    await edit(c, detail_text(info), kb.detail(cid, ops.can_restart(info["name"])))


@router.callback_query(F.data.startswith("c:"))
async def detail(c: CallbackQuery, ops: Docker):
    await c.answer()
    await show_detail(c, ops, c.data.split(":", 1)[1])


@router.callback_query(F.data.startswith("l:"))
async def container_logs(c: CallbackQuery, ops: Docker):
    await c.answer()
    cid = c.data.split(":", 1)[1]
    try:
        text = await asyncio.to_thread(ops.logs, cid)
    except DockerException:
        return await edit(c, "⚠️ Не удалось получить логи.", kb.logs(cid))
    text = html.escape(text[-3500:]) or "(пусто)"
    await edit(c, f"📜 <b>Логи</b> (последние строки)\n<pre>{text}</pre>", kb.logs(cid))


@router.callback_query(F.data.startswith("r:"))
async def restart_confirm(c: CallbackQuery, ops: Docker):
    cid = c.data.split(":", 1)[1]
    try:
        info = await asyncio.to_thread(ops.basic, cid)
    except DockerException:
        return await c.answer("Контейнер не найден", show_alert=True)
    if not ops.can_restart(info["name"]):
        return await c.answer("Этот контейнер защищён от перезапуска", show_alert=True)
    await edit(
        c,
        f"♻️ Перезапустить <b>{html.escape(info['name'])}</b>?\n"
        "Соединения клиентов на это время прервутся.",
        kb.confirm(f"rc:{cid}", f"c:{cid}", "✅ Да, перезапустить"),
    )
    await c.answer()


@router.callback_query(F.data.startswith("rc:"))
async def restart_do(c: CallbackQuery, ops: Docker):
    cid = c.data.split(":", 1)[1]
    await c.answer()
    try:
        info = await asyncio.to_thread(ops.basic, cid)
        if not ops.can_restart(info["name"]):
            return await edit(c, "Этот контейнер защищён от перезапуска.", kb.refresh("ctrs"))
        log.warning("RESTART container=%s by user=%s", info["name"], c.from_user.id)
        await edit(c, f"⏳ Перезапускаю <b>{html.escape(info['name'])}</b>…")
        await asyncio.to_thread(ops.restart, cid)
    except DockerException:
        log.exception("restart failed")
        return await edit(c, "⚠️ Не удалось перезапустить.", kb.refresh("ctrs"))
    await asyncio.sleep(3)
    await show_detail(c, ops, cid)


@router.callback_query(F.data == "hr")
async def reboot_confirm(c: CallbackQuery, settings):
    if not settings.allow_host_reboot:
        return await c.answer("Перезагрузка сервера отключена", show_alert=True)
    await edit(
        c,
        "⚠️ <b>Перезагрузить весь сервер?</b>\n"
        "Упадут Marzban, бот и всё остальное. Обычно сервер возвращается за 1–3 минуты.",
        kb.confirm("hrc", "menu", "✅ Да, перезагрузить сервер"),
    )
    await c.answer()


@router.callback_query(F.data == "hrc")
async def reboot_do(c: CallbackQuery, ops: Docker, settings):
    if not settings.allow_host_reboot:
        return await c.answer("Перезагрузка сервера отключена", show_alert=True)
    await c.answer()
    log.warning("HOST REBOOT by user=%s", c.from_user.id)
    await edit(c, "⏳ Перезагружаю сервер… Бот вернётся сам и напишет, когда поднимется.")
    try:
        await asyncio.to_thread(ops.reboot_host)
    except DockerException:
        log.exception("reboot failed")
        await edit(c, "⚠️ Не удалось запустить перезагрузку.", kb.refresh("menu"))
