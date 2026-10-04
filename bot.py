from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
import threading
import requests
from config import ADMIN_IDS, IBAN_INFO, SERVICES, SMS_API_KEY, SMS_API_URL, SUPPORT_USERNAME, BOT_TOKEN
from database import create_order, get_order, init_db, register_user, update_order_status
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


# Render panelinin "Live" vermesi için hafif web sunucusu
class SimpleHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Anka Onay Bot is alive and running!")

  def log_message(self, format, *args):
    pass  # Gereksiz HTTP log kirliliğini önler


def run_web_server():
  port = int(os.environ.get("PORT", 10000))
  server = HTTPServer(("0.0.0.0", port), SimpleHandler)
  server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  register_user(user.id, user.username or user.first_name)

  keyboard = [
      [
          InlineKeyboardButton(
              "👑 VIP ÜRÜN KATALOĞU & NUMARA AL", callback_data="catalog"
          )
      ],
      [
          InlineKeyboardButton(
              "💬 7/24 Canlı Destek", url=f"https://t.me/{SUPPORT_USERNAME}"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      f"✨ **ANKA ONAY PREMİUM SİSTEMİNE HOŞ GELDİNİZ** ✨\n\n"
      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
      f"👤 **Müşteri:** `{user.first_name}`\n"
      f"🆔 **ID:** `{user.id}`\n"
      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
      f"🔥 Piyasanın en hızlı ve güvenilir SMS onay servisindesiniz.\n"
      f"🚀 Alışverişe başlamak için aşağıdaki **VIP Ürün Kataloğu** butonuna tıklayın."
  )

  if update.message:
    await update.message.reply_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )
  elif update.callback_query:
    await update.callback_query.edit_message_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  user_id = query.from_user.id
  data = query.data

  if data == "catalog":
    keyboard = []
    for key, val in SERVICES.items():
      keyboard.append([
          InlineKeyboardButton(
              f"✨ {val['name']} ➔ 💰 {val['price']} TL",
              callback_data=f"sel_{key}",
          )
      ])
    keyboard.append(
        [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            "💎 **VIP ÜRÜN VE SERVİS KATALOĞU** 💎\n\n"
            "Lütfen sahip olmak istediğiniz numarayı seçin:\n"
            "👇 *Seçtiğiniz ürünün fiyatı ve IBAN bilgileri ekrana gelecektir.*"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("sel_"):
    srv_key = data.split("_", 1)[1]
    service_info = SERVICES.get(srv_key)
    price = service_info["price"]

    order_id = create_order(user_id, srv_key, price)

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ödemeyi Yaptım / Bildir",
                callback_data=f"paid_{order_id}",
            )
        ],
        [InlineKeyboardButton("🔙 Ürün Kataloğuna Dön", callback_data="catalog")],
    ]
    await query.edit_message_text(
        text=(
            f"🛒 **SİPARİŞ VE ÖDEME ONAY EKRANI**\n\n"
            f"📦 Seçilen Ürün: **{service_info['name']}**\n"
            f"🏷 Ödenecek Net Tutar: **{price} TL**\n"
            f"🆔 Sipariş Numarası: `#{order_id}`\n\n"
            f"{IBAN_INFO}\n"
            f"⚠️ **Nasıl Alınır?** Yukarıdaki IBAN adresine tutarı gönderdikten sonra **'Ödemeyi Yaptım / Bildir'** butonuna basın. Yönetici onayından hemen sonra numaranız gelecektir."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

  elif data.startswith("paid_"):
    order_id = int(data.split("_")[1])
    order = get_order(order_id)

    if not order:
      await query.edit_message_text(text="❌ Sipariş bulunamadı.")
      return

    service_info = SERVICES.get(order[1])

    # Admin'e şık onay/red butonlu bildirim
    admin_text = (
        f"🔔 **YENİ ÖDEME BİLDİRİMİ!**\n\n"
        f"👤 Müşteri ID: `{user_id}`\n"
        f"📦 Ürün: {service_info['name']}\n"
        f"💵 Tutar: {order[2]} TL\n"
        f"🆔 Sipariş ID: `#{order_id}`\n\n"
        f"Lütfen ödemeyi kontrol edip karar verin:"
    )

    admin_keyboard = [
        [
            InlineKeyboardButton(
                "✅ ONAYLA (Numarayı Ver)", callback_data=f"adm_ok_{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ REDDET", callback_data=f"adm_no_{order_id}"
            )
        ],
    ]

    for admin_id in ADMIN_IDS:
      try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(admin_keyboard),
            parse_mode="Markdown",
        )
      except Exception:
        pass

    await query.edit_message_text(
        text=(
            f"⏳ **ÖDEME BİLDİRİMİNİZ ALINDI!**\n\n"
            f"Sipariş No: `#{order_id}`\n"
            f"Yönetici ödemenizi kontrol ediyor. Onaylandığı an numaranız bu sohbet üzerinden otomatik olarak teslim edilecektir."
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data.startswith("adm_ok_") and user_id in ADMIN_IDS:
    order_id = int(data.split("_")[2])
    order = get_order(order_id)

    if not order or order[3] != "pending_payment":
      await query.answer(
          "Bu sipariş zaten onaylanmış veya işlem görmüş!", show_alert=True
      )
      return

    target_user_id = order[0]
    srv_key = order[1]
    service_info = SERVICES.get(srv_key)

    # API'den numara çekme
    try:
      price_res = requests.get(
          SMS_API_URL,
          params={
              "api_key": SMS_API_KEY,
              "action": "getPrices",
              "service": service_info["service_code"],
              "country": service_info["country"],
          },
          timeout=10,
      ).json()

      max_price = 500.0
      country_data = price_res.get(str(service_info["country"]), {})
      for op_name, op_info in country_data.items():
        if "cost" in op_info:
          max_price = float(op_info["cost"])
          break
    except Exception:
      max_price = 500.0

    try:
      num_res = requests.get(
          SMS_API_URL,
          params={
              "api_key": SMS_API_KEY,
              "action": "getNumberV2",
              "service": service_info["service_code"],
              "country": service_info["country"],
              "maxPriceTry": max_price,
          },
          timeout=10,
      ).json()

      if "activationId" in num_res:
        act_id = num_res["activationId"]
        phone = num_res["phoneNumber"]

        update_order_status(order_id, "completed")

        client_keyboard = [[
            InlineKeyboardButton(
                "🔄 SMS Kodunu Kontrol Et", callback_data=f"check_{act_id}"
            )
        ]]

        # Müşteriye numarayı gönder
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🎉 **ÖDEMENİZ ONAYLANDI & NUMARANIZ TESLİM EDİLDİ!**\n\n"
                f"📱 **Numara:** `{phone}`\n"
                f"📦 **Ürün:** {service_info['name']}\n"
                f"🆔 **Aktivasyon ID:** `{act_id}`\n\n"
                f"Numarayı uygulamaya yazdıktan sonra aşağıdaki butona basarak SMS kodunu ekranda görebilirsiniz."
            ),
            reply_markup=InlineKeyboardMarkup(client_keyboard),
            parse_mode="Markdown",
        )

        await query.edit_message_text(
            text=(
                f"✅ Sipariş #{order_id} başarıyla onaylandı ve numara müşteriye"
                " teslim edildi."
            )
        )
      else:
        await query.edit_message_text(
            text=(
                f"⚠️ Ödeme onaylandı ancak API'de şu an stok bulunmuyor! (Sipariş"
                f" #{order_id})"
            )
        )
    except Exception as e:
      await query.edit_message_text(
          text=f"⚠️ API Hatası: {str(e)} (Sipariş #{order_id})"
      )

  elif data.startswith("adm_no_") and user_id in ADMIN_IDS:
    order_id = int(data.split("_")[2])
    order = get_order(order_id)

    if order:
      update_order_status(order_id, "rejected")
      target_user_id = order[0]

      try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"❌ **ÖDEMENİZ ONAYLANMADI / REDDEDİLDİ**\n\n"
                f"Sipariş No: `#{order_id}`\n"
                f"Gönderdiğiniz ödeme tespit edilemedi veya eksik tutar yatırıldı. "
                f"Lütfen yetkili canlı destek ile iletişime geçin: @{SUPPORT_USERNAME}"
            ),
            parse_mode="Markdown",
        )
      except Exception:
        pass

    await query.edit_message_text(
        text=f"❌ Sipariş #{order_id} reddedildi ve müşteriye bilgi iletildi."
    )

  elif data.startswith("check_"):
    act_id = data.split("_")[1]
    try:
      status_res = requests.get(
          SMS_API_URL,
          params={
              "api_key": SMS_API_KEY,
              "action": "getStatus",
              "id": act_id,
          },
          timeout=10,
      ).text

      if "STATUS_OK" in status_res:
        code = status_res.split(":")[1]
        await query.edit_message_text(
            text=(
                f"🎊 **SMS KODUNUZ GELDİ!**\n\n🔑 Doğrulama Kodu: `{code}`\n\nİyi"
                " günlerde kullanın! ❤️"
            ),
            parse_mode="Markdown",
        )
      elif "STATUS_WAIT_CODE" in status_res:
        keyboard = [[
            InlineKeyboardButton(
                "🔄 Tekrar Kontrol Et", callback_data=f"check_{act_id}"
            )
        ]]
        await query.edit_message_text(
            text=(
                "⏳ **Kod Bekleniyor...**\n\nSMS henüz ulaşmadı. Lütfen"
                " platformdan kodu tekrar gönderin ve birkaç saniye sonra"
                " butona tekrar basın."
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
      else:
        await query.edit_message_text(text=f"ℹ️ Durum: {status_res}")
    except Exception as e:
      await query.edit_message_text(text=f"⚠️ Hata: {str(e)}")

  elif data == "main_menu":
    await start(update, context)


def main():
  # Render panelinin "Live" statüsüne geçmesi için arka planda web sunucusu başlatıyoruz
  web_thread = threading.Thread(target=run_web_server, daemon=True)
  web_thread.start()

  init_db()
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("VIP ürün kataloğu ve Render canlı web sunucusu aktif edildi...")
  app.run_polling()


if __name__ == "__main__":
  main()
