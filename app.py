import os
import requests
from config import (
    ADMIN_IDS,
    ADMIN_PASSWORD,
    BOT_TOKEN,
    IBAN_INFO,
    SERVICES,
    SMS_API_KEY,
    SMS_API_URL,
    SUPPORT_USERNAME,
)
from database import (
    add_user,
    create_deposit_request,
    create_order_db,
    get_all_deposits,
    get_all_orders,
    get_all_users,
    get_deposit_request,
    get_user_by_credentials,
    get_user_by_id,
    init_db,
    set_user_balance_manual,
    update_deposit_status,
    update_user_balance,
)
from flask import Flask, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)


# Telegram Botuna bildirim gönderme fonksiyonu
def send_telegram_admin_notification(text):
  if not BOT_TOKEN:
    return
  for admin_id in ADMIN_IDS:
    try:
      requests.get(
          f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
          params={"chat_id": admin_id, "text": text, "parse_mode": "Markdown"},
          timeout=5,
      )
    except Exception:
      pass


# --- HTML ŞABLONLARI (Ultra VIP & Karanlık Tema) ---

BASE_STYLE = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>
    body { background-color: #07090e; color: #f1f5f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .navbar { background: rgba(13, 17, 23, 0.95); backdrop-filter: blur(10px); border-bottom: 1px solid #21262d; }
    .card-vip { background: #161b22; border: 1px solid #30363d; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); transition: all 0.3s ease; }
    .card-vip:hover { border-color: #f59e0b; transform: translateY(-4px); }
    .btn-vip { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #000; font-weight: 700; border: none; border-radius: 10px; }
    .btn-vip:hover { background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: #fff; }
    .badge-balance { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); padding: 6px 14px; border-radius: 30px; font-weight: bold; }
    .support-badge { position: fixed; bottom: 25px; right: 25px; z-index: 1000; background: #25d366; color: white; padding: 12px 22px; border-radius: 50px; text-decoration: none; font-weight: bold; box-shadow: 0 6px 20px rgba(37,211,102,0.4); }
    .support-badge:hover { color: white; background: #20ba5a; }
</style>
"""

AUTH_HTML = (
    """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>VIP Giriş & Kayıt - Anka Onay</title>
    """
    + BASE_STYLE
    + """
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container" style="max-width: 450px;">
        <div class="card-vip p-4 p-md-5">
            <div class="text-center mb-4">
                <h2 class="fw-bold text-warning"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY</h2>
                <p class="text-muted small">Elit SMS Onay ve Hizmet Platformu</p>
            </div>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-{{ 'danger' if cat=='error' else 'success' }} py-2 small">{{ msg }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <ul class="nav nav-pills nav-fill mb-4 bg-dark p-1 rounded-3" id="pills-tab" role="tablist">
                <li class="nav-item">
                    <button class="nav-link active fw-bold text-warning" id="login-tab" data-bs-toggle="pill" data-bs-target="#login" type="button">Giriş Yap</button>
                </li>
                <li class="nav-item">
                    <button class="nav-link fw-bold text-light" id="register-tab" data-bs-toggle="pill" data-bs-target="#register" type="button">Kayıt Ol</button>
                </li>
            </ul>

            <div class="tab-content" id="pills-tabContent">
                <div class="tab-pane fade show active" id="login">
                    <form action="/login" method="POST">
                        <div class="mb-3">
                            <label class="form-label text-muted small">Kullanıcı Adı</label>
                            <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-muted small">Şifre</label>
                            <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
                        </div>
                        <button type="submit" class="btn btn-vip w-100 py-2 mt-2">GİRİŞ YAP</button>
                    </form>
                </div>
                <div class="tab-pane fade" id="register">
                    <form action="/register" method="POST">
                        <div class="mb-3">
                            <label class="form-label text-muted small">Kullanıcı Adı Seç</label>
                            <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-muted small">Şifre Belirle</label>
                            <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
                        </div>
                        <button type="submit" class="btn btn-vip w-100 py-2 mt-2">HESAP OLUŞTUR</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
)

INDEX_HTML = (
    """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>VIP Ürün Kataloğu - Anka Onay</title>
    """
    + BASE_STYLE
    + """
</head>
<body>
    <nav class="navbar navbar-dark px-4 py-3">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold fs-4 text-warning" href="/"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY VIP</a>
            <div class="d-flex align-items-center gap-3">
                <span class="badge-balance"><i class="fa-solid fa-wallet me-1"></i> {{ user.balance }} TL</span>
                <a href="/deposit" class="btn btn-outline-warning btn-sm fw-bold"><i class="fa-solid fa-plus me-1"></i> Bakiye Yükle</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm"><i class="fa-solid fa-right-from-bracket"></i></a>
            </div>
        </div>
    </nav>

    <div class="container my-5">
        <div class="text-center mb-5">
            <h1 class="fw-bold display-6 text-warning">✨ ELİT ÜRÜN & NUMARA KATALOĞU ✨</h1>
            <p class="text-muted">Bakiyenizle anında numara satın alabilir, sistemden anında SMS kodunuzu çekebilirsiniz.</p>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert alert-{{ 'danger' if cat=='error' else 'success' }} mb-4">{{ msg }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row g-4">
            {% for key, val in services.items() %}
            <div class="col-md-4">
                <div class="card-vip p-4 h-100 d-flex flex-column justify-content-between">
                    <div>
                        <h4 class="fw-bold mb-3 text-white">{{ val.name }}</h4>
                        <div class="fs-4 text-warning fw-bold mb-4">💰 {{ val.price }} TL</div>
                    </div>
                    <form action="/buy/{{ key }}" method="POST" onsubmit="return confirm('Bu ürünü satın almak istediğinize emin misiniz? Bakiyenizden düşecektir.');">
                        <button type="submit" class="btn btn-vip w-100 py-2"><i class="fa-solid fa-bolt me-2"></i> HEMEN NUMARA AL</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <a href="https://t.me/{{ support_username }}" target="_blank" class="support-badge">
        <i class="fa-brands fa-telegram me-2"></i> Canlı Destek
    </a>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
)

DEPOSIT_HTML = (
    """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Bakiye Yükle - Anka Onay</title>
    """
    + BASE_STYLE
    + """
</head>
<body>
    <nav class="navbar navbar-dark px-4 py-3">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold text-warning" href="/"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY VIP</a>
            <a href="/" class="btn btn-outline-light btn-sm">← Katalogaya Dön</a>
        </div>
    </nav>

    <div class="container my-5" style="max-width: 650px;">
        <div class="card-vip p-4 p-md-5">
            <h3 class="fw-bold text-warning text-center mb-4"><i class="fa-solid fa-wallet me-2"></i>BAKİYE YÜKLEME EKRANI</h3>
            
            <div class="p-3 bg-dark rounded border border-secondary mb-4">
                <h5 class="text-info mb-3">🏦 IBAN Bilgileri</h5>
                <p class="mb-1">Banka: <strong>{{ iban.bank }}</strong></p>
                <p class="mb-1">Alıcı: <strong>{{ iban.name }}</strong></p>
                <p class="mb-0">IBAN: <code class="text-warning fs-5">{{ iban.iban }}</code></p>
            </div>

            <p class="text-muted small">Lütfen yukarıdaki IBAN adresine göndermek istediğiniz tutarı yatırdıktan sonra aşağıdaki formu doldurun. Yönetici onayladığı an bakiyeniz hesabınıza geçecektir.</p>

            <form action="/deposit" method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted small">Yatırılan Tutar (TL)</label>
                    <input type="number" step="0.01" name="amount" class="form-control bg-dark text-white border-secondary" placeholder="Örn: 250" required>
                </div>
                <button type="submit" class="btn btn-vip w-100 py-3"><i class="fa-solid fa-paper-plane me-2"></i> ÖDEMEYİ BİLDİR / TALEP OLUŞTUR</button>
            </form>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
)

ORDER_SUCCESS_HTML = (
    """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Numara Teslimat - Anka Onay</title>
    """
    + BASE_STYLE
    + """
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container text-center" style="max-width: 600px;">
        <div class="card-vip p-5 shadow-lg">
            <div class="text-success display-3 mb-3"><i class="fa-solid fa-circle-check"></i></div>
            <h2 class="fw-bold text-success mb-3">Sipariş Başarılı!</h2>
            <p class="text-muted">Numaranız API üzerinden başarıyla temin edildi.</p>
            
            <div class="p-4 bg-dark rounded border border-success mb-4">
                <p class="mb-1 text-muted small">Satın Alınan Numara:</p>
                <h1 class="text-warning fw-bold font-monospace">{{ phone }}</h1>
            </div>

            <p class="text-muted small">Numarayı uygulamaya yazdıktan sonra SMS kodunu ekranda görmek için butona basın:</p>
            <a href="/sms/check/{{ activation_id }}" class="btn btn-vip w-100 py-3 fw-bold mb-3"><i class="fa-solid fa-sms me-2"></i> SMS KODUNU KONTROL ET</a>
            <a href="/" class="text-decoration-none text-muted">← Ana Katalogaya Dön</a>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
)

ADMIN_LOGIN_HTML = (
    """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Admin Giriş - Aklomanti</title>
    """
    + BASE_STYLE
    + """
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
    <div class="container" style="max-width: 400px;">
        <div class="card-vip p-4 shadow-lg">
            <h3 class="fw-bold text-center text-warning mb-4"><i class="fa-solid fa-lock me-2"></i>YÖNETİCİ GİRİŞİ</h3>
            <form method="POST">
                <div class="mb-3">
                    <input type="password" name="password" class="form-control bg-dark text-white border-secondary" placeholder="Admin Şifresi" required>
                </div>
                <button type="submit" class="btn btn-vip w-100 py-2">GİRİŞ YAP</button>
            </form>
        </div>
    </div>
</body>
</html>
"""
)

ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Elit Yönetim Paneli - Anka Onay</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #07090e; color: #f1f5f9; font-family: 'Segoe UI'; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
        .table { color: #f1f5f9; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark px-4 py-3 bg-dark border-bottom border-secondary">
        <a class="navbar-brand fw-bold text-warning" href="/admin/panel"><i class="fa-solid fa-crown me-2"></i>AKLOMANTİ YÖNETİM PANELİ</a>
        <a href="/admin/logout" class="btn btn-outline-danger btn-sm">Çıkış Yap</a>
    </nav>

    <div class="container my-5">
        <!-- Bakiye Yükleme Talepleri -->
        <h3 class="fw-bold mb-3 text-warning">💳 Bakiye Yükleme Bildirimleri</h3>
        <div class="card p-4 shadow-lg mb-5">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanıcı</th>
                            <th>Tutar</th>
                            <th>Durum</th>
                            <th>Tarih</th>
                            <th>İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in deposits %}
                        <tr>
                            <td>#{{ d[0] }}</td>
                            <td>{{ d[1] }}</td>
                            <td class="text-warning fw-bold">{{ d[2] }} TL</td>
                            <td>
                                {% if d[3] == 'pending' %}<span class="badge bg-warning text-dark">Onay Bekliyor</span>
                                {% elif d[3] == 'approved' %}<span class="badge bg-success">Onaylandı</span>
                                {% endif %}
                            </td>
                            <td>{{ d[4] }}</td>
                            <td>
                                {% if d[3] == 'pending' %}
                                    <a href="/admin/deposit/approve/{{ d[0] }}" class="btn btn-success btn-sm"><i class="fa-solid fa-check"></i> Onayla & Bakiyeyi Yükle</a>
                                {% else %}
                                    <span class="text-muted">Tamamlandı</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Kullanıcılar & Manuel Bakiye Yükleme -->
        <h3 class="fw-bold mb-3 text-info">👥 Kayıtlı Kullanıcılar & Manuel Bakiye Düzenle</h3>
        <div class="card p-4 shadow-lg mb-5">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanıcı Adı</th>
                            <th>Bakiye</th>
                            <th>Kayıt Tarihi</th>
                            <th>Manuel Bakiye Ekle/Ayarla</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for u in users %}
                        <tr>
                            <td>#{{ u[0] }}</td>
                            <td>{{ u[1] }}</td>
                            <td class="text-warning fw-bold">{{ u[2] }} TL</td>
                            <td>{{ u[3] }}</td>
                            <td>
                                <form action="/admin/user/balance/{{ u[0] }}" method="POST" class="d-flex gap-2" style="max-width: 300px;">
                                    <input type="number" step="0.01" name="new_balance" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="Yeni Bakiye" required>
                                    <button type="submit" class="btn btn-primary btn-sm text-nowrap">Güncelle</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tüm Satın Alımlar -->
        <h3 class="fw-bold mb-3 text-success">🛒 Tüm Satın Alım Geçmişi</h3>
        <div class="card p-4 shadow-lg">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanıcı</th>
                            <th>Hizmet</th>
                            <th>Ücret</th>
                            <th>Numara</th>
                            <th>Tarih</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for o in orders %}
                        <tr>
                            <td>#{{ o[0] }}</td>
                            <td>{{ o[1] }}</td>
                            <td>{{ services.get(o[2], {}).get('name', o[2]) }}</td>
                            <td class="text-warning fw-bold">{{ o[3] }} TL</td>
                            <td><code class="text-success">{{ o[4] }}</code></td>
                            <td>{{ o[6] }}</td>
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


# --- ROUTE (SAYFA) İŞLEMLERİ ---


@app.route("/")
def index():
  if not session.get("user_id"):
    return redirect(url_for("auth_page"))
  user = get_user_by_id(session["user_id"])
  return render_template_string(
      INDEX_HTML, user=user, services=SERVICES, support_username=SUPPORT_USERNAME
  )


@app.route("/auth")
def auth_page():
  if session.get("user_id"):
    return redirect(url_for("index"))
  return render_template_string(AUTH_HTML)


@app.route("/login", methods=["POST"])
def login():
  username = request.form.get("username")
  password = request.form.get("password")
  user = get_user_by_credentials(username, password)
  if user:
    session["user_id"] = user[0]
    return redirect(url_for("index"))
  else:
    from flask import flash

    flash("Kullanıcı adı veya şifre hatalı!", "error")
    return redirect(url_for("auth_page"))


@app.route("/register", methods=["POST"])
def register():
  username = request.form.get("username")
  password = request.form.get("password")
  success = add_user(username, password)
  from flask import flash

  if success:
    flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
  else:
    flash("Bu kullanıcı adı zaten alınmış!", "error")
  return redirect(url_for("auth_page"))


@app.route("/logout")
def logout():
  session.pop("user_id", None)
  return redirect(url_for("auth_page"))


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
  if not session.get("user_id"):
    return redirect(url_for("auth_page"))

  if request.method == "POST":
    try:
      amount = float(request.form.get("amount"))
    except ValueError:
      amount = 0.0

    if amount > 0:
      user = get_user_by_id(session["user_id"])
      req_id = create_deposit_request(user[0], amount)

      # Telegram Botuna bildirim gönder
      send_telegram_admin_notification(
          f"🔔 *YENİ BAKİYE YÜKLEME TALEBİ!*\n\n"
          f"👤 Kullanıcı: `{user[1]}`\n"
          f"💵 Tutar: `{amount} TL`\n"
          f"🆔 Talep ID: `#{req_id}`\n\n"
          f"Lütfen Admin Paneline girip onaylayın."
      )

      from flask import flash

      flash(
          "Bakiye yükleme talebiniz alındı! Yönetici onayından sonra bakiyeniz"
          " yüklenecektir.",
          "success",
      )
      return redirect(url_for("index"))

  return render_template_string(DEPOSIT_HTML, iban=IBAN_INFO)


@app.route("/buy/<service_key>", methods=["POST"])
def buy_service(service_key):
  if not session.get("user_id"):
    return redirect(url_for("auth_page"))

  user = get_user_by_id(session["user_id"])
  service = SERVICES.get(service_key)

  if not service or user[2] < service["price"]:
    from flask import flash

    flash("Bakiyeniz bu ürün için yetersiz! Lütfen bakiye yükleyin.", "error")
    return redirect(url_for("index"))

  # SMS API'den numara çekme
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

      # Bakiyeden düş ve siparişi kaydet
      update_user_balance(user[0], -service["price"])
      create_order_db(user[0], service_key, service["price"], phone, act_id)

      return render_template_string(
          ORDER_SUCCESS_HTML, phone=phone, activation_id=act_id
      )
    else:
      from flask import flash

      flash(
          "Şu an API'de bu ürün için stok bulunmuyor. Lütfen daha sonra tekrar"
          " deneyin.",
          "error",
      )
      return redirect(url_for("index"))
  except Exception as e:
    from flask import flash

    flash(f"API Hatası: {str(e)}", "error")
    return redirect(url_for("index"))


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
      return f"<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>🎉 SMS Kodunuz: <span style='color:green;'>{code}</span></h2><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
    elif "STATUS_WAIT_CODE" in status_res:
      return "<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>⏳ Kod bekleniyor... Lütfen sayfayı birkaç saniye sonra yenileyin.</h2><meta http-equiv='refresh' content='5'><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
    else:
      return f"<h3 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>Durum: {status_res}</h3><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
  except Exception as e:
    return f"Hata: {str(e)}"


# --- ADMIN PANELİ (Şifre: aklomanti) ---


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

  users = get_all_users()
  deposits = get_all_deposits()
  orders = get_all_orders()

  return render_template_string(
      ADMIN_PANEL_HTML,
      users=users,
      deposits=deposits,
      orders=orders,
      services=SERVICES,
  )


@app.route("/admin/deposit/approve/<int:req_id>")
def admin_approve_deposit(req_id):
  if not session.get("admin"):
    return redirect(url_for("admin_login"))

  dep = get_deposit_request(req_id)
  if dep and dep[3] == "pending":
    update_deposit_status(req_id, "approved")
    update_user_balance(dep[1], dep[2])  # Kullanıcıya bakiyeyi ekle

  return redirect(url_for("admin_panel"))


@app.route("/admin/user/balance/<int:user_id>", methods=["POST"])
def admin_manual_balance(user_id):
  if not session.get("admin"):
    return redirect(url_for("admin_login"))

  try:
    new_bal = float(request.form.get("new_balance"))
    set_user_balance_manual(user_id, new_bal)
  except ValueError:
    pass

  return redirect(url_for("admin_panel"))


@app.route("/admin/logout")
def admin_logout():
  session.pop("admin", None)
  return redirect(url_for("admin_login"))


if __name__ == "__main__":
  init_db()
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
