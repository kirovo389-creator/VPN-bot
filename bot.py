"""Telegram demo bot. It never processes real payments or creates real VPN keys."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from database import (
    activate_demo,
    add_device,
    create_demo_payment,
    delete_device,
    get_account,
    init_db,
    upsert_user,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vpn-demo")

NODES = [
    ("🇩🇪", "Германия", "DE"),
    ("🇳🇱", "Нидерланды", "NL"),
    ("🇫🇮", "Финляндия", "FI"),
    ("🇵🇱", "Польша", "PL"),
    ("🇺🇸", "США", "US"),
]


def main_menu(web_url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Моя подписка", callback_data="account"),
         InlineKeyboardButton(text="📱 Мои устройства", callback_data="devices")],
        [InlineKeyboardButton(text="🌍 Локации", callback_data="locations"),
         InlineKeyboardButton(text="💳 Тарифы и оплата", callback_data="plans")],
    ]
    if web_url and web_url.startswith("https://"):
        rows.insert(0, [InlineKeyboardButton(text="🌐 Открыть личный кабинет", web_app=WebAppInfo(url=web_url))])
    rows.append([InlineKeyboardButton(text="🎁 Активировать демо на 30 дней", callback_data="activate_demo")])
    rows.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def device_keyboard(devices: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for device in devices:
        rows.append([InlineKeyboardButton(
            text=f"🗑 Удалить: {device['name']}",
            callback_data=f"del:{device['id']}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Добавить демо-устройство", callback_data="add_device")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_text(user_id: int) -> str:
    data = get_account(user_id)
    sub = data["subscription"]
    if not sub:
        return (
            "👤 <b>Моя подписка</b>\n\n"
            "Статус: не активна\n"
            "Устройства: 0/5\n\n"
            "Нажми «Активировать демо», чтобы проверить интерфейс. "
            "Это тестовый режим — деньги не списываются и VPN-доступ не создаётся."
        )
    expires = datetime.fromisoformat(sub["expires_at"]).astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    return (
        "👤 <b>Моя подписка</b>\n\n"
        f"Тариф: <b>{sub['plan']}</b>\n"
        f"Статус: <b>{sub['status']}</b>\n"
        f"Окончание: <b>{expires}</b>\n"
        f"Устройства: <b>{len(data['devices'])}/5</b>\n\n"
        "DEMO: активность подписки имитируется. Настоящего VPN-профиля пока нет."
    )


async def on_start(message: Message, bot: Bot, web_url: str | None) -> None:
    user = message.from_user
    if not user:
        return
    upsert_user(user.id, user.username, user.first_name)
    await message.answer(
        "🚀 <b>VPN Control — DEMO</b>\n\n"
        "Тестовый кабинет управления подпиской. Здесь можно посмотреть тариф, устройства и локации.\n\n"
        "⚠️ Это демонстрация: реальные платежи и VPN-подключения отключены.",
        reply_markup=main_menu(web_url),
    )


async def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set. Add it as a GitHub Actions secret; do not paste it into source code.")

    init_db()
    web_url = os.getenv("WEB_APP_URL", "").strip() or None
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await on_start(message, bot, web_url)

    @dp.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Это демо-бот. Команды: /start — меню, /account — подписка, /devices — устройства.\n"
            "Настоящие оплаты, конфигурации и подключение к VPS пока не включены."
        )

    @dp.message(Command("account"))
    async def account_handler(message: Message) -> None:
        if message.from_user:
            upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            await message.answer(account_text(message.from_user.id), reply_markup=main_menu(web_url))

    @dp.message(Command("devices"))
    async def devices_handler(message: Message) -> None:
        if not message.from_user:
            return
        upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        devices = get_account(message.from_user.id)["devices"]
        if not devices:
            body = "📱 <b>Мои устройства</b>\n\nПока нет добавленных устройств."
        else:
            body = "📱 <b>Мои устройства</b>\n\n" + "\n".join(
                f"• {d['name']} — {d['platform']}" for d in devices
            )
        await message.answer(body, reply_markup=device_keyboard(devices))

    @dp.callback_query(F.data == "home")
    async def home_handler(query: CallbackQuery) -> None:
        await query.message.edit_text("🚀 <b>VPN Control — DEMO</b>\n\nВыбери раздел:", reply_markup=main_menu(web_url))
        await query.answer()

    @dp.callback_query(F.data == "account")
    async def account_callback(query: CallbackQuery) -> None:
        await query.message.edit_text(account_text(query.from_user.id), reply_markup=main_menu(web_url))
        await query.answer()

    @dp.callback_query(F.data == "devices")
    async def devices_callback(query: CallbackQuery) -> None:
        devices = get_account(query.from_user.id)["devices"]
        body = "📱 <b>Мои устройства</b>\n\n"
        body += "\n".join(f"• {d['name']} — {d['platform']}" for d in devices) if devices else "Пока устройств нет."
        body += "\n\nВ демо добавляется запись устройства, но VPN-конфигурация не выдаётся."
        await query.message.edit_text(body, reply_markup=device_keyboard(devices))
        await query.answer()

    @dp.callback_query(F.data == "add_device")
    async def add_device_callback(query: CallbackQuery) -> None:
        data = get_account(query.from_user.id)
        if len(data["devices"]) >= 5:
            await query.answer("Лимит — 5 устройств.", show_alert=True)
            return
        try:
            item = add_device(query.from_user.id, f"Демо-устройство {len(data['devices']) + 1}", "Unknown")
            await query.message.edit_text(
                f"✅ Добавлена демо-запись: <b>{item['name']}</b>.\n"
                "В реальном сервисе здесь создаётся отдельный клиент и VPN-профиль.",
                reply_markup=device_keyboard(get_account(query.from_user.id)["devices"]),
            )
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return
        await query.answer()

    @dp.callback_query(F.data.startswith("del:"))
    async def delete_device_callback(query: CallbackQuery) -> None:
        device_id = query.data.split(":", 1)[1]
        delete_device(query.from_user.id, device_id)
        devices = get_account(query.from_user.id)["devices"]
        body = "📱 <b>Мои устройства</b>\n\n" + ("\n".join(f"• {d['name']} — {d['platform']}" for d in devices) if devices else "Устройств нет.")
        await query.message.edit_text(body, reply_markup=device_keyboard(devices))
        await query.answer("Удалено")

    @dp.callback_query(F.data == "activate_demo")
    async def activate_demo_callback(query: CallbackQuery) -> None:
        upsert_user(query.from_user.id, query.from_user.username, query.from_user.first_name)
        activate_demo(query.from_user.id)
        create_demo_payment(query.from_user.id)
        await query.message.edit_text(
            account_text(query.from_user.id) + "\n\n🎁 <b>Демо активировано.</b> Это не платёж и не реальный VPN-доступ.",
            reply_markup=main_menu(web_url),
        )
        await query.answer("Демо активировано")

    @dp.callback_query(F.data == "locations")
    async def locations_callback(query: CallbackQuery) -> None:
        text = "🌍 <b>Локации — демонстрация</b>\n\n" + "\n".join(
            f"{flag} {name} ({code}) — тестовая карточка, сервер не подключён"
            for flag, name, code in NODES
        )
        await query.message.edit_text(text, reply_markup=main_menu(web_url))
        await query.answer()

    @dp.callback_query(F.data == "plans")
    async def plans_callback(query: CallbackQuery) -> None:
        await query.message.edit_text(
            "💳 <b>Тарифы</b>\n\n"
            "DEMO Premium — тестовая подписка на 30 дней.\n"
            "Цена: 0 ₽ (симуляция).\n\n"
            "Реальная платёжная система не подключена. Нажми «Активировать демо» для проверки сценария.",
            reply_markup=main_menu(web_url),
        )
        await query.answer()

    @dp.callback_query(F.data == "help")
    async def help_callback(query: CallbackQuery) -> None:
        await query.message.edit_text(
            "ℹ️ <b>Помощь</b>\n\n"
            "Это тестовый проект VPN Control. Демо показывает интерфейс подписки и устройств. "
            "До покупки VPS и подключения платёжного провайдера VPN-ключи и реальные оплаты отключены.",
            reply_markup=main_menu(web_url),
        )
        await query.answer()

    run_seconds = int(os.getenv("BOT_RUN_SECONDS", "0") or "0")
    log.info("Starting demo bot; run_seconds=%s", run_seconds or "unlimited")
    try:
        if run_seconds > 0:
            await asyncio.wait_for(dp.start_polling(bot), timeout=run_seconds)
        else:
            await dp.start_polling(bot)
    except asyncio.TimeoutError:
        log.info("Demo window finished.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
