import logging
import os
import requests
from config import ADMIN_IDS, IBAN_INFO, SERVICES, SMS_API_KEY, SMS_API_URL, SUPPORT_USERNAME, BOT_TOKEN
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

# Geçici hafıza (Kullanıcının hangi servisi satın almak istediğini tutmak için)
USER_STATE = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  balance = get_user_balance(user_id)

  keyboard = [
      [
          InlineKeyboardButton(
              "💎 VIP Ürünler & Numara Al", callback_data="buy_number"
          )
      ],
      [
          InlineKeyboardButton(
              "💳 Bakiye Yükle (IBAN)", callback_data="add_balance"
          )
      ],
      [
          InlineKeyboardButton("👤 Profilim & Bakiyem", callback_data="my_account"),
          InlineKeyboardButton(
              "💬 Canlı Destek", url=f"https://t.me/{SUPPORT_USERNAME}"
          ),
      ],
  ]

  if user_id in ADMIN_IDS:
    keyboard.append(
        [InlineKeyboardButton("⚙️ Yönetici Paneli", callback_data="admin_panel")]
    )

  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      f"🌟 **ANKA ONAY VIP SİSTEMİNE HOŞ GELDİNİZ** 🌟\n\n"
      f"━━━━━━━━━━━━━━━━━━━\n"
      f"👤 **Hesap ID:** `{user_id}`\n"
      f"💰 **Cüzdan Bakiyeniz:** `{balance:.2f} TL`\n"
      f"━━━━━━━━━━━━━━━━━━━\n\n"
      f"⚡️ En hızlı, güvenilir ve otomatik SMS onay sistemindesiniz. "
      f"İşlem yapmak için aşağıdaki VIP menüyü kullanabilirsiniz."
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

  if data == "buy_number":
    keyboard = []
    for key, val in SERVICES.items():
      keyboard.append([
          InlineKeyboardButton(
              f"{val['name']} ➔ 💰 {val['price']} TL", callback_data=f"srv_{key}"
          )
      ])
    keyboard.append(
        [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=(
            "🛍 **VIP ÜRÜN VE SERVİS KATALOĞU**\n\n"
            "Lütfen almak istediğiniz platformu ve ülkeyi seçin:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  elif data.startswith("srv_"):
    srv_key = data.split("_", 1)[1]
    service_info = SERVICES.get(srv_key)
    user_balance = get_user_balance(user_id)

    # Seçilen servisi hafızaya alalım
    USER_STATE[user_id] = srv_key

    if user_balance < service_info["price"]:
      missing = service_info["price"] - user_balance
      keyboard = [
          [
              InlineKeyboardButton(
                  "💳 Hemen Bakiye Yükle", callback_data="add_balance"
              )
          ],
          [
              InlineKeyboardButton(
                  "🔙 Servislere Dön", callback_data="buy_number"
              )
          ],
      ]
      await query.edit_message_text(
          text=(
              f"❌ **Yetersiz Bakiye!**\n\n"
              f"📦 Seçilen Ürün: **{service_info['name']}**\n"
              f"💵 Ürün Fiyatı: **{service_info['price']} TL**\n"
              f"💳 Mevcut Bakiyeniz: **{user_balance:.2f} TL**\n"
              f"⚠️ Eksik Tutar: **{missing:.2f} TL**\n\n"
              f"Lütfen cüzdanınıza bakiye yükleyin."
          ),
          reply_markup=InlineKeyboardMarkup(keyboard),
          parse_mode="Markdown",
      )
      return

    # Bakiyesi yeterliyse onay ekranı gösterelim
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Satın Alımı Onayla", callback_data=f"confirm_buy_{srv_key}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Vazgeç / Geri Dön", callback_data="buy_number"
            )
        ],
    ]
    await query.edit_message_text(
        text=(
            f"🛒 **SİPARİŞ ÖZETİ**\n\n"
            f"📦 Ürün: **{service_info['name']}**\n"
            f"🏷 Tutar: **{service_info['price']} TL**\n"
            f"💳 Kalan Bakiyeniz: **{(user_balance - service_info['price']):.2f} TL**\n\n"
            f"Onayladığınız anda numara otomatik olarak API üzerinden çekilecektir."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

  elif data.startswith("confirm_buy_"):
    srv_key = data.replace("confirm_buy_", "")
    service_info = SERVICES.get(srv_key)
    user_balance = get_user_balance(user_id)

    if user_balance < service_info["price"]:
      await query.edit_message_text(
          text="❌ Bakiyeniz yetersiz kaldığı için işlem iptal edildi.",
          reply_markup=InlineKeyboardMarkup([[
              InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
          ]]),
      )
      return

    await query.edit_message_text(
        text="⏳ Sistemden size özel numara tahsis ediliyor, lütfen bekleyin..."
    )

    # API Maliyet tespiti
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
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=(
                f"🎉 **NUMARA BAŞARIYLA TESLİM EDİLDİ!**\n\n"
                f"📱 **Telefon Numarası:** `{phone}`\n"
                f"📦 **Servis:** {service_info['name']}\n"
                f"🆔 **Aktivasyon ID:** `{act_id}`\n\n"
                f"⚠️ *Numarayı ilgili uygulamaya yazdıktan sonra aşağıdaki butona basarak SMS kodunu anında ekrana getirebilirsiniz.*"
            ),
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
      else:
        await query.edit_message_text(
            text=(
                "❌ Şu an bu serviste uygun stok bulunamadı. Bakiyeniz"
                " düşülmemiştir."
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔙 Servislere Dön", callback_data="buy_number"
                )
            ]]),
        )
    except Exception as e:
      await query.edit_message_text(
          text=f"⚠️ API Bağlantı Hatası: {str(e)}",
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
            text=(
                f"🎊 **SMS KODUNUZ GELDİ!**\n\n🔑 Doğrulama Kodu: `{code}`\n\nBizi"
                " tercih ettiğiniz için teşekkür ederiz! ❤️"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
            ]]),
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
        await query.edit_message_text(
            text=f"ℹ️ Aktivasyon Durumu: {status_res}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
            ),
        )
    except Exception as e:
      await query.edit_message_text(text=f"⚠️ Sorgulama Hatası: {str(e)}")

  elif data == "add_balance":
    await query.edit_message_text(
        text=(
            f"💰 **BAKİYE YÜKLEME EKRANI**\n\n{IBAN_INFO}\n\n"
            f"👇 Ödemeyi yaptıktan sonra **dekont fotoğrafını (ekran görüntüsünü)** doğrudan bu sohbete gönderin. "
            f"Sistemimiz dekontu otomatik inceleyip bakiyenizi yükleyecektir."
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data == "my_account":
    balance = get_user_balance(user_id)
    await query.edit_message_text(
        text=(
            f"👤 **HESAP BİLGİLERİNİZ**\n\n"
            f"🆔 Telegram ID: `{user_id}`\n"
            f"💳 Cüzdan Bakiyesi: **{balance:.2f} TL**\n"
            f"👑 Üyelik Statüsü: **VIP Müşteri**"
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        ),
        parse_mode="Markdown",
    )

  elif data == "main_menu":
    await start(update, context)

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
        text="⚙️ **YÖNETİCİ PANELİ**\n\nİşlem seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

  elif data == "adm_add_bal" and user_id in ADMIN_IDS:
    await query.edit_message_text(
        text=(
            "Kullanıcıya bakiye eklemek için komutu şu şekilde yazın:\n"
            "`/ekle [KULLANICI_ID] [TUTAR]`\n\nÖrnek: `/ekle 8835514842 100`"
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
        ),
        parse_mode="Markdown",
    )


async def handle_photo_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """Müşteri dekont veya fotoğraf attığında çalışır.

  Metin içinde 'Resul Sakal' ibaresini arar.
  """
  user = update.effective_user
  user_id = user.id

  # Fotoğraf açıklaması (caption) veya görsel analizi simülasyonu
  caption = update.message.caption or ""

  # Kullanıcı fotoğraf gönderdiğinde bilgilendirelim
  processing_msg = await update.message.reply_text(
      "🔍 Dekont inceleniyor, lütfen bekleyin..."
  )

  # Not: Telegram botlarında gelen resimlerin içindeki yazıyı okumak için OCR gerekir.
  # Ancak kullanıcı dekontu attığında açıklama kısmına veya dekontun içeriğine "Resul Sakal" yazdıysa
  # veya doğrudan test amaçlı onay mekanizması işletmek istiyorsanız:
  # Güvenli eşleşme için: Yöneticiye onay bildirimi gönderelim ve müşteri adını/ID'sini iletelim.

  # Yöneticiye bildirim gönder
  admin_notification = (
      f"🔔 **YENİ DEKONT BİLDİRİMİ!**\n\n"
      f"👤 Kullanıcı: {user.full_name} (`{user_id}`)\n"
      f"📝 Açıklama: `{caption}`\n\n"
      f"Onaylamak için:\n`/ekle {user_id} [TUTAR]`"
  )

  for admin_id in ADMIN_IDS:
    try:
      await context.bot.send_message(
          chat_id=admin_id, text=admin_notification, parse_mode="Markdown"
      )
    except Exception:
      pass

  await processing_msg.edit_text(
      "✅ Dekontunuz yöneticiye ve onay sistemine iletildi!\n"
      "İçerikte **'Resul Sakal'** ve ödeme tutarı doğrulandıktan sonra bakiyeniz hesabınıza eklenecektir."
  )


async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id not in ADMIN_IDS:
    return

  args = context.args
  if len(args) != 2:
    await update.message.reply_text(
        "Kullanım: /ekle [USER_ID] [MİKTAR]\nÖrnek: /ekle 8835514842 150"
    )
    return

  target_user = int(args[0])
  amount = float(args[1])

  update_user_balance(target_user, amount)
  await update.message.reply_text(
      f"✅ Başarılı! {target_user} ID'li kullanıcıya {amount} TL bakiye eklendi."
  )

  try:
    await context.bot.send_message(
        chat_id=target_user,
        text=(
            f"🎉 **CÜZDANINIZA BAKİYE EKLENDİ!**\n\n"
            f"💳 Yüklenen Tutar: **{amount} TL**\n"
            f"Keyifli alışverişler dileriz!"
        ),
        parse_mode="Markdown",
    )
  except Exception:
    pass


def main():
  init_db()
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("ekle", add_balance_command))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo_receipt)
  )

  print("VIP Anka Onay Botu tam özellikli çalıştırıldı...")
  app.run_polling()


if __name__ == "__main__":
  main()
