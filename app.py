import os
import requests
from config import ADMIN_PASSWORD, IBAN_INFO, SERVICES, SMS_API_KEY, SMS_API_URL, SUPPORT_USERNAME
from database import (
    create_order,
    get_all_orders,
    get_order,
    init_db,
    update_order_complete,
    update_order_status,
)
from flask import Flask, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- HTML ŞABLONLARI ---

INDEX_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VIP Anka Onay - Ürün Kataloğu</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px); border-bottom: 1px solid #1e293b; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); border-color: #3b82f6; }
        .btn-vip { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; border: none; font-weight: 600; }
        .btn-vip:hover { background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); color: white; }
        .support-badge { position: fixed; bottom: 20px; right: 20px; z-index: 1000; background: #25d366; color: white; padding: 12px 20px; border-radius: 50px; text-decoration: none; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .support-badge:hover { color: white; background: #20ba5a; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark px-4 py-3">
        <a class="navbar-brand fw-bold fs-4" href="/"><i class="fa-solid fa-crown text-warning me-2"></i> ANKA ONAY VIP</a>
        <a href="/admin" class="btn btn-outline-light btn-sm"><i class="fa-solid fa-lock me-1"></i> Admin Girişi</a>
    </nav>

    <div class="container my-5">
        <div class="text-center mb-5">
            <h1 class="fw-bold display-6">💎 Premium SMS Onay Servisi</h1>
            <p class="text-muted">Anında teslimat, güvenli altyapı ve yüksek kaliteli numaralar.</p>
        </div>

        <div class="row g-4">
            {% for key, val in services.items() %}
            <div class="col-md-4">
                <div class="card p-4 h-100 d-flex flex-column justify-content-between">
                    <div>
                        <h4 class="fw-bold mb-3">{{ val.name }}</h4>
                        <div class="fs-4 text-warning fw-bold mb-3">💰 {{ val.price }} TL</div>
                    </div>
                    <form action="/order/create" method="POST">
                        <input type="hidden" name="service_key" value="{{ key }}">
                        <div class="mb-3">
                            <input type="text" name="customer_name" class="form-control bg-dark text-white border-secondary" placeholder="Adınız Soyadınız" required>
                        </div>
                        <button type="submit" class="btn btn-vip w-100 py-2"><i class="fa-solid fa-cart-shopping me-2"></i> Satın Al / IBAN Öde</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <a href="https://t.me/{{ support_username }}" target="_blank" class="support-badge">
        <i class="fa-brands fa-telegram me-2"></i> Canlı Destek
    </a>
</body>
</html>
"""

PAYMENT_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ödeme Ekranı - Anka Onay</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .btn-success-custom { background: #10b981; color: white; font-weight: bold; border: none; }
        .btn-success-custom:hover { background: #059669; color: white; }
    </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container" style="max-width: 600px;">
        <div class="card p-4 shadow-lg">
            <h3 class="fw-bold text-center text-warning mb-4"><i class="fa-solid fa-wallet me-2"></i> ÖDEME BİLDİRİM EKRANI</h3>
            
            <div class="alert alert-dark border-secondary">
                <p class="mb-1">📦 Seçilen Ürün: <strong>{{ service.name }}</strong></p>
                <p class="mb-1">🏷 Ödenecek Tutar: <strong class="text-warning">{{ service.price }} TL</strong></p>
                <p class="mb-0">🆔 Sipariş Numarası: <strong>#{{ order_id }}</strong></p>
            </div>

            <div class="p-3 bg-dark rounded border border-secondary mb-4">
                <h5 class="text-info mb-3">🏦 IBAN Bilgileri</h5>
                <p class="mb-1">Banka: <strong>{{ iban.bank }}</strong></p>
                <p class="mb-1">Alıcı: <strong>{{ iban.name }}</strong></p>
                <p class="mb-0">IBAN: <code class="text-warning fs-5">{{ iban.iban }}</code></p>
            </div>

            <p class="text-muted small text-center">Lütfen yukarıdaki IBAN adresine tam tutarı gönderdikten sonra aşağıdaki butona tıklayın. Yönetici onayından hemen sonra numaranız panelde belirecektir.</p>

            <form action="/order/paid/{{ order_id }}" method="POST">
                <button type="submit" class="btn btn-success-custom w-100 py-3 fs-5"><i class="fa-solid fa-check-circle me-2"></i> Ödemeyi Yaptım / Bildir</button>
            </form>
            <div class="text-center mt-3">
                <a href="/" class="text-decoration-none text-muted">← Ana Sayfaya Dön</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

STATUS_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sipariş Durumu</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
    </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container text-center" style="max-width: 600px;">
        <div class="card p-5 shadow-lg">
            {% if order[3] == 'pending_payment' %}
                <div class="spinner-border text-warning mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
                <h3 class="fw-bold mb-3">Ödemeniz Kontrol Ediliyor</h3>
                <p class="text-muted">Sipariş ID: <strong>#{{ order_id }}</strong></p>
                <p>Yönetici ödemenizi kontrol ediyor. Onaylandığı an numaranız bu ekranda görünecektir.</p>
                <button onclick="location.reload();" class="btn btn-outline-light mt-3"><i class="fa-solid fa-rotate me-2"></i> Durumu Yenile</button>
            {% elif order[3] == 'completed' %}
                <div class="text-success display-4 mb-3"><i class="fa-solid fa-circle-check"></i></div>
                <h3 class="fw-bold text-success mb-3">Ödemeniz Onaylandı!</h3>
                <div class="p-3 bg-dark rounded border border-success mb-4">
                    <p class="mb-1 text-muted">Numaranız:</p>
                    <h2 class="text-warning fw-bold font-monospace">{{ order[4] }}</h2>
                </div>
                <p class="text-muted small">Numarayı ilgili uygulamaya girdikten sonra SMS kodunu almak için aşağıdaki butonu kullanabilirsiniz.</p>
                <a href="/sms/check/{{ order[5] }}" class="btn btn-warning w-100 py-2 fw-bold"><i class="fa-solid fa-sms me-2"></i> SMS Kodunu Kontrol Et</a>
            {% elif order[3] == 'rejected' %}
                <div class="text-danger display-4 mb-3"><i class="fa-solid fa-circle-xmark"></i></div>
                <h3 class="fw-bold text-danger mb-3">Ödeme Reddedildi</h3>
                <p class="text-muted">Gönderdiğiniz ödeme onaylanmadı. Lütfen canlı destek ile iletişime geçin.</p>
            {% endif %}
            <div class="mt-4">
                <a href="/" class="text-decoration-none text-muted">← Ana Sayfaya Dön</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Admin Giriş</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI'; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
    </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container" style="max-width: 400px;">
        <div class="card p-4 shadow-lg">
            <h3 class="fw-bold text-center mb-4">🔐 Yönetici Girişi</h3>
            <form method="POST">
                <div class="mb-3">
                    <input type="password" name="password" class="form-control bg-dark text-white border-secondary" placeholder="Admin Şifresi" required>
                </div>
                <button type="submit" class="btn btn-primary w-100">Giriş Yap</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Admin Paneli - Anka Onay</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI'; }
        .card { background: #1e293b; border: 1px solid #334155; }
        .table { color: #f8fafc; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark px-4 py-3 bg-dark border-bottom border-secondary">
        <a class="navbar-brand fw-bold" href="/admin">⚡ Yönetim Paneli</a>
        <a href="/admin/logout" class="btn btn-outline-danger btn-sm">Çıkış Yap</a>
    </nav>

    <div class="container my-5">
        <h2 class="fw-bold mb-4">Gelen Siparişler ve Ödeme Bildirimleri</h2>
        <div class="card p-4 shadow-lg">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Müşteri</th>
                            <th>Ürün</th>
                            <th>Tutar</th>
                            <th>Durum</th>
                            <th>Numara / İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for order in orders %}
                        <tr>
                            <td>#{{ order[0] }}</td>
                            <td>{{ order[1] }}</td>
                            <td>{{ services.get(order[2], {}).get('name', order[2]) }}</td>
                            <td class="text-warning fw-bold">{{ order[3] }} TL</td>
                            <td>
                                {% if order[4] == 'pending_payment' %}<span class="badge bg-warning text-dark">Ödeme Bekliyor</span>
                                {% elif order[4] == 'completed' %}<span class="badge bg-success">Onaylandı</span>
                                {% elif order[4] == 'rejected' %}<span class="badge bg-danger">Reddedildi</span>
                                {% endif %}
                            </td>
                            <td>
                                {% if order[4] == 'pending_payment' %}
                                    <a href="/admin/approve/{{ order[0] }}" class="btn btn-success btn-sm me-1"><i class="fa-solid fa-check"></i> Onayla & Ver</a>
                                    <a href="/admin/reject/{{ order[0] }}" class="btn btn-danger btn-sm"><i class="fa-solid fa-xmark"></i> Reddet</a>
                                {% else %}
                                    <code>{{ order[5] if order[5] else 'İşlem Tamam' }}</code>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""


# --- ROUTE (SAYFA) TANIMLARI ---


@app.route("/")
def index():
  return render_template_string(
      INDEX_HTML, services=SERVICES, support_username=SUPPORT_USERNAME
  )


@app.route("/order/create", methods=["POST"])
def create_order_route():
  customer_name = request.form.get("customer_name")
  service_key = request.form.get("service_key")
  service = SERVICES.get(service_key)

  if not service:
    return redirect(url_for("index"))

  order_id = create_order(customer_name, service_key, service["price"])
  return redirect(url_for("payment_page", order_id=order_id))


@app.route("/order/payment/<int:order_id>")
def payment_page(order_id):
  order = get_order(order_id)
  if not order:
    return "Sipariş bulunamadı", 404
  service = SERVICES.get(order[1])
  return render_template_string(
      PAYMENT_HTML, order_id=order_id, service=service, iban=IBAN_INFO
  )


@app.route("/order/paid/<int:order_id>", methods=["POST"])
def order_paid(order_id):
  return redirect(url_for("order_status", order_id=order_id))


@app.route("/order/status/<int:order_id>")
def order_status(order_id):
  order = get_order(order_id)
  if not order:
    return "Sipariş bulunamadı", 404
  return render_template_string(STATUS_HTML, order_id=order_id, order=order)


@app.route("/sms/check/<act_id>")
def sms_check(act_id):
  try:
    status_res = requests.get(
        SMS_API_URL,
        params={"api_key": SMS_API_KEY, "action": "getStatus", "id": act_id},
        timeout=10,
    ).text

    if "STATUS_OK" in status_res:
      code = status_res.split(":")[1]
      return f"<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>🎉 SMS Kodunuz: <span style='color:green;'>{code}</span></h2>"
    elif "STATUS_WAIT_CODE" in status_res:
      return "<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>⏳ Kod bekleniyor... Lütfen sayfayı birkaç saniye sonra yenileyin.</h2><meta http-equiv='refresh' content='5'>"
    else:
      return f"<h3 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>Durum: {status_res}</h3>"
  except Exception as e:
    return f"Hata: {str(e)}"


# --- ADMIN PANELİ ROUTE'LARI ---


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
  if request.method == "POST":
    if request.form.get("password") == ADMIN_PASSWORD:
      session["admin"] = True
      return redirect(url_for("admin_panel"))
  return render_template_string(ADMIN_LOGIN_HTML)


@app.route("/admin/panel")
def admin_panel():
  if not session.get("admin"):
    return redirect(url_for("admin_login"))
  orders = get_all_orders()
  return render_template_string(
      ADMIN_PANEL_HTML, orders=orders, services=SERVICES
  )


@app.route("/admin/approve/<int:order_id>")
def admin_approve(order_id):
  if not session.get("admin"):
    return redirect(url_for("admin_login"))

  order = get_order(order_id)
  if not order:
    return "Sipariş bulunamadı", 404

  service = SERVICES.get(order[1])

  # API'den numara çekme
  try:
    price_res = requests.get(
        SMS_API_URL,
        params={
            "api_key": SMS_API_KEY,
            "action": "getPrices",
            "service": service["service_code"],
            "country": service["country"],
        },
        timeout=10,
    ).json()

    max_price = 500.0
    country_data = price_res.get(str(service["country"]), {})
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
            "service": service["service_code"],
            "country": service["country"],
            "maxPriceTry": max_price,
        },
        timeout=10,
    ).json()

    if "activationId" in num_res:
      act_id = num_res["activationId"]
      phone = num_res["phoneNumber"]
      update_order_complete(order_id, phone, act_id)
    else:
      update_order_complete(order_id, "Stok Bulunamadı!", "")
  except Exception as e:
    update_order_complete(order_id, f"API Hatası: {str(e)}", "")

  return redirect(url_for("admin_panel"))


@app.route("/admin/reject/<int:order_id>")
def admin_reject(order_id):
  if not session.get("admin"):
    return redirect(url_for("admin_login"))
  update_order_status(order_id, "rejected")
  return redirect(url_for("admin_panel"))


@app.route("/admin/logout")
def admin_logout():
  session.pop("admin", None)
  return redirect(url_for("admin_login"))


if __name__ == "__main__":
  init_db()
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
