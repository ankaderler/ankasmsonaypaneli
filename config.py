import os

BOT_TOKEN = "8839137520:AAH4b1X74EV4Cpp0eoeTfMfRw_GapDjZVQ8"
SMS_API_KEY = "osms_7f193a3fe65448a9380061c1b56e9fdc29f49c67e89eb3dd"
SMS_API_URL = "https://onaylasms.com.tr/stubs/handler_api.php"

# Senin Admin / Yönetici Telegram ID'n
ADMIN_IDS = [8835514842]

SUPPORT_USERNAME = "ResulSakal"

# IBAN ve Ödeme Bilgileri
IBAN_INFO = (
    "🏦 **ÖDEME BİLGİLERİ**\n\n"
    "• **Banka:** Ziraat Bankası / Diğer\n"
    "• **Alıcı Adı Soyadı:** Resul Sakal\n"
    "• **IBAN:** `TR62 0006 2000 5000 0006 8107 73`\n"
)

# VIP Bayraklı Servisler ve Fiyatlar
SERVICES = {
    "tr_wa": {
        "name": "🇹🇷 Türkiye WhatsApp",
        "service_code": "wa",
        "country": 1,
        "price": 250.0,
    },
    "tr_tg": {
        "name": "🇹🇷 Türkiye Telegram",
        "service_code": "tg",
        "country": 1,
        "price": 200.0,
    },
    "ph_wa": {
        "name": "🇵🇭 Filipinler WhatsApp",
        "service_code": "wa",
        "country": 62,
        "price": 150.0,
    },
    "us_tg": {
        "name": "🇺🇸 Amerika Telegram",
        "service_code": "tg",
        "country": 187,
        "price": 200.0,
    },
    "tr_ig": {
        "name": "🇹🇷 Instagram Türkiye",
        "service_code": "ig",
        "country": 1,
        "price": 60.0,
    },
    "ca_wa": {
        "name": "🇨🇦 WhatsApp Kanada",
        "service_code": "wa",
        "country": 36,
        "price": 200.0,
    },
    "gg_mail": {
        "name": "🌐 Google Gmail",
        "service_code": "go",
        "country": 1,
        "price": 50.0,
    },
    "tr_disc": {
        "name": "🇹🇷 Discord Türkiye",
        "service_code": "ds",
        "country": 1,
        "price": 100.0,
    },
    "tr_hopi": {
        "name": "🇹🇷 Hopi Türkiye",
        "service_code": "hopi",
        "country": 1,
        "price": 100.0,
    },
}
