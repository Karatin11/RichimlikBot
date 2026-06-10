from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

from scheduler import start_scheduler
from sheets import (
    add_history,
    get_admin_id,
    get_all_people,
    get_next_person,
    get_person_by_tr,
    increment_count,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN      = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID  = os.getenv("GROUP_CHAT_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
TIMEZONE       = os.getenv("TIMEZONE", "Asia/Tashkent")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()



def admin_id() -> int:
    return get_admin_id(SPREADSHEET_ID)


def build_keyboard(doer_tr: int, skipped_trs_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Bajarildi!",       callback_data=f"done:{doer_tr}:{skipped_trs_str}")],
        [InlineKeyboardButton(text="📢 Guruhga yuborish", callback_data=f"togroup:{doer_tr}")],
        [InlineKeyboardButton(text="⏭ Keyingisi",         callback_data=f"skip:{doer_tr}:{skipped_trs_str}")],
    ])


def reminder_text(person: dict, skipped_names: list[str]) -> str:
    skip_line = ""
    if skipped_names:
        skip_line = f"\n⚠️ O'tkazib yuborildi: <b>{', '.join(skipped_names)}</b>\n"

    people   = get_all_people(SPREADSHEET_ID)
    next_p   = get_next_person(people, [person["tr"]])
    next_line = f"⏭ Keyingisi: <b>{next_p['name']}</b>\n" if next_p else ""

    return (
        f"╔══════════════════╗\n"
        f"   🥤 <b>ICHIMLIK NAVBATI</b>\n"
        f"╚══════════════════╝\n"
        f"{skip_line}\n"
        f"Bugun navbat:\n"
        f"  👤 <b>{person['name']}</b>  (#{person['tr']})\n\n"
        f"📊 Umumiy: <b>{person['count']}</b> marta\n"
        f"{next_line}"
        f"─────────────────────\n"
        f"Quyidagi tugmalardan birini bosing 👇"
    )



async def send_admin_reminder(skip_trs: list[int] = None):
    aid = admin_id()
    if not aid:
        logger.warning("ADMIN_ID not set in Sozlamalar B2!")
        return

    skip_trs   = skip_trs or []
    people     = get_all_people(SPREADSHEET_ID)
    person     = get_next_person(people, skip_trs)

    if not person:
        await bot.send_message(aid,
            "⚠️ <b>Bugun hamma o'tkazib yubordi!</b>\nAdmin hal qilsin.",
            parse_mode="HTML")
        return

    skipped_names = [p["name"] for p in people if p["tr"] in skip_trs]
    skipped_str   = ",".join(str(t) for t in skip_trs) if skip_trs else "0"

    await bot.send_message(
        aid,
        reminder_text(person, skipped_names),
        parse_mode="HTML",
        reply_markup=build_keyboard(person["tr"], skipped_str),
    )



@dp.callback_query(F.data.startswith("done:"))
async def cb_done(call: CallbackQuery):
    parts      = call.data.split(":")
    doer_tr    = int(parts[1])

    people = get_all_people(SPREADSHEET_ID)
    doer   = get_person_by_tr(people, doer_tr)
    if not doer:
        await call.answer("Xatolik!", show_alert=True)
        return

    increment_count(SPREADSHEET_ID, doer["row"])
    skipped_trs  = [int(x) for x in parts[2].split(",") if x and x != "0"]
    skipped_names = [p["name"] for p in people if p["tr"] in skipped_trs]
    note = f"O'rniga keldi ({', '.join(skipped_names)} o'rniga)" if skipped_names else ""
    add_history(SPREADSHEET_ID, doer["name"], note)

    updated_people = get_all_people(SPREADSHEET_ID)
    next_p = get_next_person(updated_people)
    next_line = f"\n⏭ Keyingi navbat: <b>{next_p['name']}</b>" if next_p else ""

    await call.message.edit_text(
        f"╔══════════════════╗\n"
        f"      ✅ <b>BAJARILDI!</b>\n"
        f"╚══════════════════╝\n\n"
        f"👤 <b>{doer['name']}</b> ichimlik olib keldi!\n"
        f"📊 Umumiy: <b>{doer['count'] + 1}</b> marta"
        f"{next_line}",
        parse_mode="HTML",
    )
    await call.answer("✅ Belgilandi!")

    await bot.send_message(
        GROUP_CHAT_ID,
        f"╔══════════════════╗\n"
        f"      ✅ <b>BAJARILDI!</b>\n"
        f"╚══════════════════╝\n\n"
        f"Bugun ichimlik olib keldi:\n"
        f"  👤 <b>{doer['name']}</b>\n\n"
        f"🙌 Rahmat! 🥤🧃",
        parse_mode="HTML",
    )



@dp.callback_query(F.data.startswith("togroup:"))
async def cb_togroup(call: CallbackQuery):
    doer_tr = int(call.data.split(":")[1])
    people  = get_all_people(SPREADSHEET_ID)
    doer    = get_person_by_tr(people, doer_tr)
    if not doer:
        await call.answer("Xatolik!", show_alert=True)
        return

    await bot.send_message(
        GROUP_CHAT_ID,
        f"╔══════════════════╗\n"
        f"   🥤 <b>ICHIMLIK NAVBATI</b>\n"
        f"╚══════════════════╝\n\n"
        f"Bugun ichimlik olib kelish navbati:\n\n"
        f"        👤 <b>{doer['name']}</b>\n\n"
        f"─────────────────────\n"
        f"Iltimos, unutmang! 🥤🧃",
        parse_mode="HTML",
    )
    await call.answer("📢 Guruhga yuborildi!")



@dp.callback_query(F.data.startswith("skip:"))
async def cb_skip(call: CallbackQuery):
    parts       = call.data.split(":")
    skipped_tr  = int(parts[1])
    old_skipped = [int(x) for x in parts[2].split(",") if x and x != "0"]
    new_skipped = list(set(old_skipped + [skipped_tr]))

    people      = get_all_people(SPREADSHEET_ID)
    next_person = get_next_person(people, new_skipped)

    if not next_person:
        await call.message.edit_text(
            "⚠️ <b>Bugun hamma o'tkazib yubordi!</b>\nAdmin hal qilsin.",
            parse_mode="HTML",
        )
        await call.answer()
        return

    skipped_names = [p["name"] for p in people if p["tr"] in new_skipped]
    skipped_str   = ",".join(str(t) for t in new_skipped)

    await call.message.edit_text(
        reminder_text(next_person, skipped_names),
        parse_mode="HTML",
        reply_markup=build_keyboard(next_person["tr"], skipped_str),
    )
    await call.answer()



@dp.message(Command("list"), F.chat.type == "private")
async def cmd_list(message: Message):
    people = get_all_people(SPREADSHEET_ID)
    if not people:
        await message.reply("📋 Ro'yxat bo'sh.")
        return

    # Build ordered queue: current navbatchi first, then next 4
    current = get_next_person(people)
    if not current:
        await message.reply("📋 Ro'yxat bo'sh.")
        return

    queue = [current]
    skipped = [current["tr"]]
    for _ in range(min(4, len(people) - 1)):
        nxt = get_next_person(people, skipped)
        if not nxt:
            break
        queue.append(nxt)
        skipped.append(nxt["tr"])

    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    lines = [f"🥤  <b>{current['name']}</b>  — {current['count']}x"]
    for i, p in enumerate(queue[1:]):
        lines.append(f"{icons[i]}  {p['name']}  — {p['count']}x")

    await message.reply(
        f"╔══════════════════╗\n"
        f"   📋 <b>NAVBAT RO'YXATI</b>\n"
        f"╚══════════════════╝\n\n"
        + "\n".join(lines),
        parse_mode="HTML",
    )


@dp.message(Command("note"), F.chat.type == "private")
async def cmd_eslatma(message: Message):
    if message.from_user.id != admin_id():
        await message.reply("⛔ Faqat admin uchun!")
        return
    await send_admin_reminder()
    await message.reply("✅ Eslatma yuborildi!")


@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message):
    aid = admin_id()
    if message.from_user.id != aid:
        await message.reply(
            "👋 Salom! Men <b>IchimlikBot</b> man.\n\n"
            "Guruhda /list yoki /yordam yozing.",
            parse_mode="HTML",
        )
        return

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 List"), KeyboardButton(text="🔔 Note")]
        ],
        resize_keyboard=True,
    )
    await message.reply(
        "╔══════════════════╗\n"
        "   🤖 <b>ADMIN PANEL</b>\n"
        "╚══════════════════╝\n\n"
        "Salom, Admin! 👋\n\n"
        "─────────────────────\n"
        "📋 <b>Guruh buyruqlari:</b>\n\n"
        "▸ /list — navbat ro'yxati\n"
        "▸ /help — yordam\n\n"
        "─────────────────────\n"
        "🔐 <b>Admin buyruqlari (shu yerda):</b>\n\n"
        "▸ /note — bugungi eslatmani\n"
        "    qayta yuborish",
        parse_mode="HTML",
        reply_markup=kb,
    )


@dp.message(F.text == "📋 List", F.chat.type == "private")
async def btn_list(message: Message):
    await cmd_list(message)


@dp.message(F.text == "🔔 Note", F.chat.type == "private")
async def btn_note(message: Message):
    if message.from_user.id != admin_id():
        await message.reply("⛔ Faqat admin!")
        return
    await send_admin_reminder()
    await message.reply("✅ Eslatma yuborildi!")


@dp.callback_query(F.data == "admin_list")
async def cb_admin_list(call: CallbackQuery):
    if call.from_user.id != admin_id():
        await call.answer("⛔ Faqat admin!", show_alert=True)
        return
    people  = get_all_people(SPREADSHEET_ID)
    current = get_next_person(people)
    if not current:
        await call.answer("Ro'yxat bo'sh.", show_alert=True)
        return
    queue   = [current]
    skipped = [current["tr"]]
    for _ in range(min(4, len(people) - 1)):
        nxt = get_next_person(people, skipped)
        if not nxt:
            break
        queue.append(nxt)
        skipped.append(nxt["tr"])
    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    lines = [f"🥤  <b>{current['name']}</b>  — {current['count']}x"]
    for i, p in enumerate(queue[1:]):
        lines.append(f"{icons[i]}  {p['name']}  — {p['count']}x")
    await call.message.answer(
        f"╔══════════════════╗\n"
        f"   📋 <b>NAVBAT RO'YXATI</b>\n"
        f"╚══════════════════╝\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )
    await call.answer()


@dp.callback_query(F.data == "admin_note")
async def cb_admin_note(call: CallbackQuery):
    if call.from_user.id != admin_id():
        await call.answer("⛔ Faqat admin!", show_alert=True)
        return
    await send_admin_reminder()
    await call.answer("✅ Eslatma yuborildi!")


@dp.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message):
    await message.reply(
        "╔══════════════════╗\n"
        "   🤖 <b>ICHIMLIK BOT</b>\n"
        "╚══════════════════╝\n\n"
        "📌 <b>Guruh buyruqlari:</b>\n\n"
        "▸ /list — navbat ro'yxati va hisoblagich\n"
        "▸ /yordam — ushbu yordam\n\n"
        "─────────────────────\n"
        "🔐 <b>Admin buyruqlari (LM):</b>\n\n"
        "▸ /eslatma — bugungi eslatmani qayta yuborish\n\n"
        "─────────────────────\n"
        "⚙️ Sozlamalar Google Sheets → <b>Sozlamalar</b> sahifasida:\n"
        "  B1 — eslatma vaqti (09:00)\n"
        "  B2 — admin Telegram ID",
        parse_mode="HTML",
    )






async def main():
    start_scheduler(bot, GROUP_CHAT_ID, SPREADSHEET_ID, TIMEZONE)
    logger.info("Bot started")
    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    asyncio.run(main())
