import logging
import requests
from config import ADMIN_IDS, IBAN_INFO, SERVICES, SMS_API_KEY, SMS_API_URL, SUPPORT_USERNAME, BOT_TOKEN
from database import create_order, get_order, init_db, register_user, update_order_status
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  register_user(user.id, user.username or user.first_name)

  keyboard = [
      [
          InlineKeyboardButton(
              "🌐 Web Panel & Ürün Kataloğu", callback_data="catalog"
          )
      ],
      [
          InlineKeyboardButton(
              "💬 Canlı Destek", url=f"https://t.me/{SUPPORT_USERNAME}"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      f"🌐 **ANKA ONAY WEB PANELİNE HOŞ GELDİNİZ** 🌐\n\n"
      f"━━━━━━━━━━━━━━━━━━━\n"
      f"👤 **Kayıtlı Kullanıcı:** `{user.first_name}`\n"
      f"🆔 **ID:** `{user.id}`\n"
      f"━━━━━━━━━━━━━━━━━━━\n\n"
      f"Sistemimiz tam otomatik web panel mantığıyla çalışır. "
      f"Ürün seçip ödemenizi yaptıktan sonra bildirim atarsınız, onaylandığı an numaranız anında teslim edilir."
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
              f"{val['name']} ➔ 🏷 {val['price']} TL", callback_data=f"sel_{key}"
          )
      ])
    keyboard.append(
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            "📦 **WEB PANEL ÜRÜN LİSTESİ**\n\n"
            "Satın almak istediğiniz servise tıklayarak ödeme detaylarına"
            " ulaşabilirsiniz:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("sel_"):
    srv_key = data.split("_", 1)[1]
    service_info = SERVICES.get(srv_key)
    price = service_info["price"]

    # Sipariş oluştur (Bekliyor durumunda)
    order_id = create_order(user_id, srv_key, price)

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ödemeyi Yaptım / Bildir",
                callback_data=f"paid_{order_id}",
            )
        ],
        [InlineKeyboardButton("🔙 Ürünlere Dön", callback_data="catalog")],
    ]
    await query.edit_message_text(
        text=(
            f"🛒 **SİPARİŞ VE ÖDEME EKRANI**\n\n"
            f"📦 Seçilen Ürün: **{service_info['name']}**\n"
            f"💵 Ödenecek Tutar: **{price} TL**\n"
            f"🆔 Sipariş No: `#{order_id}`\n\n"
            f"{IBAN_INFO}\n"
            f"⚠️ *Lütfen yukarıdaki tutarı IBAN adresine gönderdikten sonra alttaki 'Ödemeyi Yaptım' butonuna basın.*"
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

    # Admin'e onay bildirimi gönder
    admin_text = (
        f"🔔 **YENİ ÖDEME BİLDİRİMİ!**\n\n"
        f"👤 Müşteri ID: `{user_id}`\n"
        f"📦 Ürün: {service_info['name']}\n"
        f"💵 Tutar: {order[2]} TL\n"
        f"🆔 Sipariş ID: `#{order_id}`\n\n"
        f"Onaylamak veya Reddetmek için aşağıdaki butonları kullanın:"
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
            f"⏳ **Ödeme Bildirimi Alındı!**\n\n"
            f"Sipariş No: `#{order_id}`\n"
            f"Yönetici ödemenizi kontrol ediyor. Onaylandığı an numaranız bu sohbet üzerinden otomatik olarak teslim edilecektir."
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data.startswith("adm_ok_") and user_id in ADMIN_IDS:
    order_id = int(data.split("_")[2])
    order = get_order(order_id)

    if not order or order[3] != "pending_payment":
      await query.answer("Bu sipariş zaten onaylanmış veya işlenmiş!", show_alert=True)
      return

    target_user_id = order[0]
    srv_key = order[1]
    service_info = SERVICES.get(srv_key)

    # API'den numara çek
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
                f"Numarayı uygulamaya girip ardından aşağıdaki butondan SMS kodunu sorgulayabilirsiniz."
            ),
            reply_markup=InlineKeyboardMarkup(client_keyboard),
            parse_mode="Markdown",
        )

        await query.edit_message_text(
            text=(
                f"✅ Sipariş #{order_id} onaylandı ve numara müşteriye başarıyla"
                " teslim edildi."
            )
        )
      else:
        await query.edit_message_text(
            text=(
                f"⚠️ Ödeme onaylandı ancak API'de şu an stok yok! (Sipariş"
                f" #{order_id})"
            )
        )
    except Exception as e:
      await query.edit_message_text(
          text=f"⚠️️ API Hatası: {str(e)} (Sipariş #{order_id})"
      )

  elif data.startswith("adm_no_") and user_id in ADMIN_IDS:
    order_id = int(data.split("_")[2])
    order = get_order(order_id)

    if order:
      update_order_status(order_id, "rejected")
      target_user_id = order[0]

      # Müşteriye reddedildiğini ve canlı desteğe yönlendirildiğini bildir
      try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"❌ **ÖDEMENİZ ONAYLANMADI / REDDEDİLDİ**\n\n"
                f"Sipariş No: `#{order_id}`\n"
                f"Gönderdiğiniz ödeme tespit edilemedi veya hatalı. "
                f"Lütfen yetkili yönetici ile iletişime geçin: @{SUPPORT_USERNAME}"
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
                f"🎊 **SMS KODUNUZ GELDİ!**\n\n🔑 Kod: `{code}`\n\nİyi"
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
            text="⏳ Henüz SMS gelmedi. Lütfen biraz bekleyip tekrar kontrol edin.",
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
  init_db()
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("Web panel mantıklı ödemeli bot aktif edildi...")
  app.run_polling()


if __name__ == "__main__":
  main()
