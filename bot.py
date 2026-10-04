import logging
import requests
from config import ADMIN_IDS, IBAN_INFO, SERVICES, SMS_API_KEY, SMS_API_URL, BOT_TOKEN
from database import get_user_balance, init_db, update_user_balance
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
  user_id = update.effective_user.id
  balance = get_user_balance(user_id)

  keyboard = [
      [InlineKeyboardButton("📱 Numara Satın Al", callback_data="buy_number")],
      [InlineKeyboardButton("💰 Bakiye Yükle (IBAN)", callback_data="add_balance")],
      [InlineKeyboardButton("👤 Hesabım / Bakiyem", callback_data="my_account")],
  ]

  if user_id in ADMIN_IDS:
    keyboard.append(
        [InlineKeyboardButton("⚙️ Admin Paneli", callback_data="admin_panel")]
    )

  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(
      f"👋 Hoş geldiniz!\n\n"
      f"💳 Güncel Bakiyeniz: **{balance:.2f} TL**\n\n"
      f"Aşağıdaki menüden işlem seçebilirsiniz:",
      reply_markup=reply_markup,
      parse_mode="Markdown",
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  user_id = query.from_user.id
  data = query.data

  if data == "buy_number":
    keyboard = []
    for key, val in SERVICES.items():
      keyboard.append([
          InlineKeyboardButton(
              f"{val['name']} - {val['price']} TL", callback_data=f"srv_{key}"
          )
      ])
    keyboard.append(
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Lütfen almak istediğiniz servisi seçin:", reply_markup=reply_markup
    )

  elif data.startswith("srv_"):
    srv_key = data.split("_", 1)[1]
    service_info = SERVICES.get(srv_key)
    user_balance = get_user_balance(user_id)

    if user_balance < service_info["price"]:
      await query.edit_message_text(
          text=(
              f"❌ Bakiyeniz yetersiz!\nBu hizmet için gereken: {service_info['price']} TL\n"
              f"Mevcut Bakiyeniz: {user_balance:.2f} TL"
          ),
          reply_markup=InlineKeyboardMarkup([[
              InlineKeyboardButton(
                  "🔙 Servislere Dön", callback_data="buy_number"
              )
          ]]),
      )
      return

    # API'den getPrices çekerek güncel maliyeti öğrenip maxPriceTry belirleyelim
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

      # API'den gelen maliyeti bulalım
      # Dönüş yapısı: {"country_id": {"operator_name": {"cost": X, "count": Y}}}
      max_price = 500.0  # Varsayılan emniyet tavanı
      country_data = price_res.get(str(service_info["country"]), {})
      for op_name, op_info in country_data.items():
        if "cost" in op_info:
          max_price = float(op_info["cost"])
          break
    except Exception:
      max_price = 500.0

    # Numara Talep Et (getNumberV2)
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

        # Bakiyeden düş
        update_user_balance(user_id, -service_info["price"])

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 SMS Kodunu Kontrol Et",
                    callback_data=f"check_{act_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ İptal Et (İade)", callback_data=f"cancel_{act_id}"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=f"✅ Numara Başarıyla Alındı!\n\n"
            f"📱 **Numara:** `{phone}`\n"
            f"📦 **Servis:** {service_info['name']}\n"
            f"💵 **Ücret:** {service_info['price']} TL\n\n"
            f"Lütfen numaranızı ilgili platformda kullanın ve ardından SMS kontrolü yapın.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
      else:
        await query.edit_message_text(
            text="❌ Şuan bu serviste uygun stok bulunamadı veya bakiye yetersiz.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔙 Servislere Dön", callback_data="buy_number"
                )
            ]]),
        )
    except Exception as e:
      await query.edit_message_text(
          text=f"⚠️ API Hatası oluştu: {str(e)}",
          reply_markup=InlineKeyboardMarkup(
              [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
          ),
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
            text=f"🎉 **SMS Kodunuz:** `{code}`", parse_mode="Markdown"
        )
      elif "STATUS_WAIT_CODE" in status_res:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Tekrar Kontrol Et", callback_data=f"check_{act_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ İptal Et", callback_data=f"cancel_{act_id}"
                )
            ],
        ]
        await query.edit_message_text(
            text=(
                "⏳ Henüz SMS gelmedi. Lütfen bekleyin ve tekrar kontrol edin."
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
      else:
        await query.edit_message_text(
            text=f"ℹ️ Durum: {status_res}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
            ),
        )
    except Exception as e:
      await query.edit_message_text(text=f"⚠️ Hata: {str(e)}")

  elif data == "add_balance":
    await query.edit_message_text(
        text=f"💰 **Bakiye Yükleme Bilgileri**\n\n{IBAN_INFO}\n\n"
        f"Ödeme yaptıktan sonra yöneticiye bildirimde bulunun.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data == "my_account":
    balance = get_user_balance(user_id)
    await query.edit_message_text(
        text=f"👤 **Hesap Bilgileriniz**\n\n🆔 ID: `{user_id}`\n💳 Bakiye: **{balance:.2f} TL**",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data == "main_menu":
    balance = get_user_balance(user_id)
    keyboard = [
        [InlineKeyboardButton("📱 Numara Satın Al", callback_data="buy_number")],
        [
            InlineKeyboardButton(
                "💰 Bakiye Yükle (IBAN)", callback_data="add_balance"
            )
        ],
        [InlineKeyboardButton("👤 Hesabım / Bakiyem", callback_data="my_account")],
    ]
    if user_id in ADMIN_IDS:
      keyboard.append(
          [InlineKeyboardButton("⚙️ Admin Paneli", callback_data="admin_panel")]
      )
    await query.edit_message_text(
        text=f"👋 Ana Menü\n\nGüncel Bakiyeniz: **{balance:.2f} TL**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

  elif data == "admin_panel" and user_id in ADMIN_IDS:
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Kullanıcıya Bakiye Ekle", callback_data="adm_add_bal"
            )
        ],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        text="⚙️ **Yönetici Paneli**\n\nİşlem seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

  elif data == "adm_add_bal" and user_id in ADMIN_IDS:
    await query.edit_message_text(
        text=(
            "Kullanıcıya bakiye eklemek için komutu şu şekilde yazın:\n"
            "`/ekle [KULLANICI_ID] [TUTAR]`\n\nÖrnek: `/ekle 123456789 100`"
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        ),
        parse_mode="Markdown",
    )


async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    return

  args = context.args
  if len(args) != 2:
    await update.message.reply_text(
        "Kullanım: /ekle [USER_ID] [MİKTAR]\nÖrnek: /ekle 123456789 150"
    )
    return

  target_user = int(args[0])
  amount = float(args[1])

  update_user_balance(target_user, amount)
  await update.message.reply_text(
      f"✅ Başarılı! {target_user} ID'li kullanıcıya {amount} TL bakiye eklendi."
  )


def main():
  init_db()
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("ekle", add_balance_command))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("Bot çalıştırıldı...")
  app.run_polling()


if __name__ == "__main__":
  main()
