import os
import requests
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ---------------------------------------------------------
# BURAYA KENDİ VERİTABANI VE CONFIG AYARLARINI EKLEYEBİLİRSİN
# (Eğer config.py kullanıyorsan import edebilirsin)
# ---------------------------------------------------------
try:
  from config import ADMIN_IDS, ADMIN_PASSWORD, SERVICES, SMS_API_KEY, SMS_API_URL
except ImportError:
  # Yedek / Örnek Tanımlar (config.py yoksa patlamaması için)
  ADMIN_IDS = []
  ADMIN_PASSWORD = "admin"
  SMS_API_KEY = ""
  SMS_API_URL = "https://onaylasms.com.tr/api/v1/"
  SERVICES = {}


# Basit bir veritabanı veya geçici yardımcı fonksiyonlar (kendi yapına göre uyarlanmıştır)
def get_user_by_id(user_id):
  return (user_id, "Kullanıcı", 100.0)  # Örnek


def update_user_balance(user_id, amount):
  pass


def create_order_db(user_id, service_key, price, phone, act_id):
  pass


# Admin Paneli HTML Örneği (autocomplete="new-password" ile öneri engellendi)
ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Admin Giriş</title>
</head>
<body style="font-family: Arial; background: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh;">
    <div style="background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 300px;">
        <h3>Admin Paneli Giriş</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div style="color: red; margin-bottom: 15px; font-size: 14px;">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST">
            <label style="font-size: 14px; display: block; margin-bottom: 5px;">Şifre:</label>
            <input type="password" name="password" autocomplete="new-password" required 
                   style="width: 100%; padding: 8px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;">
            <button type="submit" style="width: 100%; background: #007bff; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer;">Giriş Yap</button>
        </form>
    </div>
</body>
</html>
"""

ORDER_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>Numara Başarılı</title></head>
<body style="font-family: Arial; text-align: center; padding: 50px;">
    <h2>Numara Başarıyla Alındı!</h2>
    <p><b>Telefon Numarası:</b> {{ phone }}</p>
    <p><b>Aktivasyon ID:</b> {{ activation_id }}</p>
    <a href="/">Ana Sayfaya Dön</a>
</body>
</html>
"""


@app.route("/")
def index():
  return "Ana Sayfa Çalışıyor! <a href='/admin'>Admin Paneli</a>"


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
  if request.method == "POST":
    password = request.form.get("password")
    if password == ADMIN_PASSWORD:
      session["is_admin"] = True
      return redirect(url_for("admin_panel"))
    else:
      flash("Hatalı şifre!", "error")
  return render_template_string(ADMIN_LOGIN_HTML)


@app.route("/admin/panel")
def admin_panel():
  if not session.get("is_admin"):
    return redirect(url_for("admin_login"))
  return "Hoş geldiniz, Admin Paneli!"


@app.route("/buy/<service_key>", methods=["POST"])
def buy_service(service_key):
  if not session.get("user_id"):
    # Test ortamı için kullanıcı yoksa varsayılan bir ID atayabiliriz veya yönlendirebiliriz
    session["user_id"] = 1

  user = get_user_by_id(session["user_id"])
  service = SERVICES.get(service_key, {"price": 10.0, "service_code": "wa", "country": "tr"})

  if not service or user[2] < service["price"]:
    flash("Bakiyeniz bu ürün için yetersiz! Lütfen bakiye yükleyin.", "error")
    return redirect(url_for("index"))

  # Fiyat sorgulama adımı
  max_price = 500.0
  try:
    price_res_raw = requests.get(
        SMS_API_URL,
        params={
            "api_key": SMS_API_KEY,
            "action": "getPrices",
            "service": service["service_code"],
            "country": service["country"],
        },
        timeout=10,
    )
    print("Fiyat API Ham Yanıtı:", price_res_raw.text)
    price_res = price_res_raw.json()

    country_data = price_res.get(str(service["country"]), {})
    for op_name, op_info in country_data.items():
      if "cost" in op_info:
        max_price = float(op_info["cost"])
        break
  except Exception as e:
    print("Fiyat API Hatası:", str(e))

  # Numara alma adımı
  try:
    num_res_raw = requests.get(
        SMS_API_URL,
        params={
            "api_key": SMS_API_KEY,
            "action": "getNumberV2",
            "service": service["service_code"],
            "country": service["country"],
            "maxPriceTry": max_price,
        },
        timeout=10,
    )
    print("Numara API Ham Yanıtı:", num_res_raw.text)
    num_res = num_res_raw.json()

    if "activationId" in num_res:
      act_id = num_res["activationId"]
      phone = num_res["phoneNumber"]

      update_user_balance(user[0], -service["price"])
      create_order_db(user[0], service_key, service["price"], phone, act_id)

      return render_template_string(
          ORDER_SUCCESS_HTML, phone=phone, activation_id=act_id
      )
    else:
      flash(
          f"API'den hata döndü: {num_res.get('message', 'Bilinmeyen hata')}",
          "error",
      )
      return redirect(url_for("index"))
  except Exception as e:
    flash(f"API Çözümleme Hatası: {str(e)}", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=True)
