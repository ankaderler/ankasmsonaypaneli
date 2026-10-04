import json
import os
import requests
from config import (
    ADMIN_IDS,
    ADMIN_PASSWORD,
    ADMIN_USER,
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


# Telegram Botuna İnline Butonlu Bildirim Gönderme
def send_telegram_deposit_notification(req_id, username, fullname, amount):
  if not BOT_TOKEN:
    return
  text = (
      f"🔔 *YENİ BAKİYE YÜKLEME TALEBİ!*\n\n"
      f"👤 Kullanıcı: `{username}`\n"
      f"💳 Gönderen Ad Soyad: *{fullname}*\n"
      f"💵 Tutar: `{amount} TL`\n"
      f"🆔 Talep ID: `#{req_id}`"
  )

  keyboard = {
      "inline_keyboard": [
          [
              {"text": "✅ Onayla ve Yükle", "callback_data": f"approve_{req_id}"},
              {"text": "❌ Reddet", "callback_data": f"reject_{req_id}"},
          ]
      ]
  }

  for admin_id in ADMIN_IDS:
    try:
      requests.post(
          f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
          json={
              "chat_id": admin_id,
              "text": text,
              "parse_mode": "Markdown",
              "reply_markup": keyboard,
          },
          timeout=5,
      )
    except Exception:
      pass


# Telegram Webhook / Güncelleme Yakalayıcı (Bot üzerinden onay/ret için)
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
  data = request.get_json()
  if "callback_query" in data:
    query = data["callback_query"]
    callback_data = query["data"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    parts = callback_data.split("_")
    action = parts[0]
    req_id = int(parts[1])

    dep = get_deposit_request(req_id)
    if dep and dep[4] == "pending":
      user_id = dep[1]
      amount = dep[2]
      if action == "approve":
        update_deposit_status(req_id, "approved")
        update_user_balance(user_id, amount)
        resp_text = (
            f"✅ *Talep #{req_id} Onaylandı!* Kullanıcıya {amount} TL eklendi."
        )
      else:
        update_deposit_status(req_id, "rejected")
        resp_text = f"❌ *Talep #{req_id} Reddedildi.*"

      # Telegram mesajını güncelle
      requests.post(
          f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
          json={
              "chat_id": chat_id,
              "message_id": message_id,
              "text": resp_text,
              "parse_mode": "Markdown",
          },
      )
  return "OK", 200


# --- CSS & ORTAK ŞABLONLAR (Mavi VIP Tema & Animasyonlu Giriş) ---

BASE_STYLE = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>
    :root {
        --primary-blue: #0ea5e9;
        --dark-bg: #030712;
        --card-bg: #0b1329;
        --border-blue: rgba(14, 165, 233, 0.3);
    }
    body { 
        background: radial-gradient(circle at 50% 20%, #0f172a 0%, #030712 100%); 
        color: #f1f5f9; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        min-height: 100vh;
    }
    .navbar { background: rgba(11, 19, 41, 0.9); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-blue); }
    .card-vip { 
        background: var(--card-bg); 
        border: 1px solid var(--border-blue); 
        border-radius: 16px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.6); 
        transition: all 0.3s ease; 
    }
    .card-vip:hover { 
        border-color: var(--primary-blue); 
        transform: translateY(-5px); 
        box-shadow: 0 15px 35px rgba(14, 165, 233, 0.2);
    }
    .btn-vip { 
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); 
        color: #fff; 
        font-weight: 700; 
        border: none; 
        border-radius: 10px; 
        box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
    }
    .btn-vip:hover { 
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); 
        color: #fff; 
    }
    .badge-balance { 
        background: rgba(14, 165, 233, 0.15); 
        color: #38bdf8; 
        border: 1px solid rgba(14, 165, 233, 0.4); 
        padding: 6px 14px; 
        border-radius: 30px; 
        font-weight: bold; 
    }
    .support-badge { 
        position: fixed; bottom: 25px; right: 25px; z-index: 1000; 
        background: #0ea5e9; color: white; padding: 12px 22px; 
        border-radius: 50px; text-decoration: none; font-weight: bold; 
        box-shadow: 0 6px 20px rgba(14,165,233,0.5); 
    }
    .support-badge:hover { color: white; background: #0284c7; }

    /* Animasyonlu Karşılama Ekranı */
    #loader-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: #030712; display: flex; flex-direction: column;
        justify-content: center; align-items: center; z-index: 9999;
        animation: fadeOut 0.8s ease 1.2s forwards;
    }
    .loader-logo {
        font-size: 2.5rem; font-weight: bold; color: #38bdf8;
        animation: pulseGlow 1.5s infinite alternate;
    }
    @keyframes pulseGlow {
        0% { text-shadow: 0 0 10px rgba(14,165,233,0.3); transform: scale(1); }
        100% { text-shadow: 0 0 25px rgba(14,165,233,0.8); transform: scale(1.05); }
    }
    @keyframes fadeOut {
        to { opacity: 0; visibility: hidden; }
    }
</style>
"""

ANIMATED_LOADER = """
<div id="loader-overlay">
    <div class="loader-logo mb-3"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY VIP</div>
    <div class="spinner-border text-info" role="status"></div>
</div>
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
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
    """
    + ANIMATED_LOADER
    + """
    <div class="container" style="max-width: 450px;">
        <div class="card-vip p-4 p-md-5">
            <div class="text-center mb-4">
                <h2 class="fw-bold text-info"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY</h2>
                <p class="text-muted small">Elit SMS Onay ve Hizmet Platformu</p>
            </div>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-{{ 'danger' if cat=='error' else 'success' }} py-2 small">{{ msg }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <ul class="nav nav-pills nav-fill mb-4 bg-dark p-1 rounded-3 border border-secondary" id="pills-tab" role="tablist">
                <li class="nav-item">
                    <button class="nav-link active fw-bold text-info" id="login-tab" data-bs-toggle="pill" data-bs-target="#login" type="button">Giriş Yap</button>
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
    """
    + ANIMATED_LOADER
    + """
    <nav class="navbar navbar-dark px-3 px-md-4 py-3">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold fs-5 text-info" href="/"><i class="fa-solid fa-crown me-2"></i>ANKA VIP</a>
            <div class="d-flex align-items-center gap-2 gap-md-3">
                <span class="badge-balance small"><i class="fa-solid fa-wallet me-1"></i> {{ user.balance }} TL</span>
                <a href="/deposit" class="btn btn-outline-info btn-sm fw-bold"><i class="fa-solid fa-plus me-1"></i> Bakiye Yükle</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm"><i class="fa-solid fa-right-from-bracket"></i></a>
            </div>
        </div>
    </nav>

    <div class="container my-5 px-3">
        <div class="text-center mb-5">
            <h1 class="fw-bold display-6 text-info">✨ ELİT ÜRÜN & NUMARA KATALOĞU ✨</h1>
            <p class="text-muted small md-fs-6">Bakiyenizle anında numara satın alabilir, sistemden SMS kodunuzu anında çekebilirsiniz.</p>
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
            <div class="col-12 col-md-6 col-lg-4">
                <div class="card-vip p-4 h-100 d-flex flex-column justify-content-between">
                    <div>
                        <h5 class="fw-bold mb-3 text-white">{{ val.name }}</h5>
                        <div class="fs-4 text-info fw-bold mb-4">💰 {{ val.price }} TL</div>
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
    <nav class="navbar navbar-dark px-3 py-3">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold text-info" href="/"><i class="fa-solid fa-crown me-2"></i>ANKA ONAY VIP</a>
            <a href="/" class="btn btn-outline-light btn-sm">← Katalogaya Dön</a>
        </div>
    </nav>

    <div class="container my-5 px-3" style="max-width: 650px;">
        <div class="card-vip p-4 p-md-5">
            <h3 class="fw-bold text-info text-center mb-4"><i class="fa-solid fa-wallet me-2"></i>BAKİYE YÜKLEME EKRANI</h3>
            
            <div class="p-3 bg-dark rounded border border-secondary mb-4">
                <h5 class="text-info mb-3">🏦 IBAN Bilgileri</h5>
                <p class="mb-1">Banka: <strong>{{ iban.bank }}</strong></p>
                <p class="mb-1">Alıcı: <strong>{{ iban.name }}</strong></p>
                <p class="mb-0">IBAN: <code class="text-info fs-6 fs-md-5">{{ iban.iban }}</code></p>
            </div>

            <p class="text-muted small">Lütfen IBAN'a ödemeyi yaptıktan sonra aşağıdaki alanlara <strong>kendi adınızı soyadınızı</strong> ve <strong>yatırdığınız tutarı</strong> yazıp bildirim gönderin.</p>

            <form action="/deposit" method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted small">Adınız Soyadınız (Havale Yapılan Hesap Sahibi)</label>
                    <input type="text" name="fullname" class="form-control bg-dark text-white border-secondary" placeholder="Örn: Ahmet Yılmaz" required>
                </div>
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
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
    <div class="container text-center" style="max-width: 600px;">
        <div class="card-vip p-4 p-md-5 shadow-lg">
            <div class="text-success display-3 mb-3"><i class="fa-solid fa-circle-check"></i></div>
            <h2 class="fw-bold text-success mb-3">Sipariş Başarılı!</h2>
            <p class="text-muted small">Numaranız API üzerinden başarıyla temin edildi.</p>
            
            <div class="p-4 bg-dark rounded border border-success mb-4">
                <p class="mb-1 text-muted small">Satın Alınan Numara:</p>
                <h2 class="text-info fw-bold font-monospace">{{ phone }}</h2>
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
    <title>Admin Giriş - Anka Onay</title>
    """
    + BASE_STYLE
    + """
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
    <div class="container" style="max-width: 400px;">
        <div class="card-vip p-4 shadow-lg">
            <h3 class="fw-bold text-center text-info mb-4"><i class="fa-solid fa-lock me-2"></i>YÖNETİCİ GİRİŞİ</h3>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-danger py-2 small">{{ msg }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted small">Kullanıcı Adı</label>
                    <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required>
                </div>
                <div class="mb-3">
                    <label class="form-label text-muted small">Şifre</label>
                    <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elit Yönetim Paneli - Anka Onay</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #030712; color: #f1f5f9; font-family: 'Segoe UI'; }
        .card { background: #0b1329; border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 12px; }
        .table { color: #f1f5f9; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark px-3 py-3 bg-dark border-bottom border-secondary">
        <a class="navbar-brand fw-bold text-info fs-6" href="/admin/panel"><i class="fa-solid fa-crown me-2"></i>YÖNETİM PANELİ</a>
        <a href="/admin/logout" class="btn btn-outline-danger btn-sm">Çıkış Yap</a>
    </nav>

    <div class="container my-5 px-3">
        <!-- Bakiye Yükleme Talepleri -->
        <h3 class="fw-bold mb-3 text-info">💳 Bakiye Yükleme Bildirimleri</h3>
        <div class="card p-3 p-md-4 shadow-lg mb-5">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle small">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanıcı</th>
                            <th>Gönderen Ad Soyad</th>
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
                            <td class="text-info fw-bold">{{ d[3] }}</td>
                            <td class="text-warning fw-bold">{{ d[2] }} TL</td>
                            <td>
                                {% if d[4] == 'pending' %}<span class="badge bg-warning text-dark">Onay Bekliyor</span>
                                {% elif d[4] == 'approved' %}<span class="badge bg-success">Onaylandı</span>
                                {% elif d[4] == 'rejected' %}<span class="badge bg-danger">Reddedildi</span>
                                {% endif %}
                            </td>
                            <td>{{ d[5] }}</td>
                            <td>
                                {% if d[4] == 'pending' %}
                                    <div class="d-flex gap-1">
                                        <a href="/admin/deposit/approve/{{ d[0] }}" class="btn btn-success btn-sm"><i class="fa-solid fa-check"></i></a>
                                        <a href="/admin/deposit/reject/{{ d[0] }}" class="btn btn-danger btn-sm"><i class="fa-solid fa-xmark"></i></a>
                                    </div>
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
        <h3 class="fw-bold mb-3 text-info">👥 Kayıtlı Kullanıcılar & Manuel Bakiye</h3>
        <div class="card p-3 p-md-4 shadow-lg mb-5">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle small">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Kullanıcı Adı</th>
                            <th>Bakiye</th>
                            <th>Kayıt Tarihi</th>
                            <th>Manuel Bakiye Düzenle</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for u in users %}
                        <tr>
                            <td>#{{ u[0] }}</td>
                            <td>{{ u[1] }}</td>
                            <td class="text-info fw-bold">{{ u[2] }} TL</td>
                            <td>{{ u[3] }}</td>
                            <td>
                                <form action="/admin/user/balance/{{ u[0] }}" method="POST" class="d-flex gap-2" style="max-width: 250px;">
                                    <input type="number" step="0.01" name="new_balance" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="Yeni Bakiye" required>
                                    <button type="submit" class="btn btn-info btn-sm text-nowrap text-dark fw-bold">Güncelle</button>
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
        <div class="card p-3 p-md-4 shadow-lg">
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle small">
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
                            <td class="text-info fw-bold">{{ o[3] }} TL</td>
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


# --- ROUTE İŞLEMLERİ ---


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
    fullname = request.form.get("fullname")
    try:
      amount = float(request.form.get("amount"))
    except ValueError:
      amount = 0.0

    if amount > 0 and fullname:
      user = get_user_by_id(session["user_id"])
      req_id = create_deposit_request(user[0], amount, fullname)

      # Telegram Botuna İnline Butonlu Bildirim Gönder
      send_telegram_deposit_notification(req_id, user[1], fullname, amount)

      from flask import flash

      flash(
          "Bakiye bildiriminiz başarıyla yönetmene iletildi. Onaylandığında"
          " bakiyeniz yüklenecektir.",
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

      update_user_balance(user[0], -service["price"])
      create_order_db(user[0], service_key, service["price"], phone, act_id)

      return render_template_string(
          ORDER_SUCCESS_HTML, phone=phone, activation_id=act_id
      )
    else:
      from flask import flash

      flash("Şu an API'de bu ürün için stok bulunmuyor.", "error")
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
      return f"<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>🎉 SMS Kodunuz: <span style='color:#0ea5e9;'>{code}</span></h2><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
    elif "STATUS_WAIT_CODE" in status_res:
      return "<h2 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>⏳ Kod bekleniyor... Lütfen sayfayı birkaç saniye sonra yenileyin.</h2><meta http-equiv='refresh' content='5'><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
    else:
      return f"<h3 style='text-align:center; margin-top:20vh; font-family:sans-serif;'>Durum: {status_res}</h3><div style='text-align:center;'><a href='/'>← Ana Sayfaya Dön</a></div>"
  except Exception as e:
    return f"Hata: {str(e)}"


# --- ADMIN PANELİ (Kullanıcı Adı: adim, Şifre: aklomanti) ---


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
  if request.method == "POST":
    if (
        request.form.get("username") == ADMIN_USER
        and request.form.get("password") == ADMIN_PASSWORD
    ):
      session["admin"] = True
      return redirect(url_for("admin_panel"))
    else:
      from flask import flash

      flash("Kullanıcı adı veya şifre hatalı!", "error")
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
  if dep and dep[4] == "pending":
    update_deposit_status(req_id, "approved")
    update_user_balance(dep[1], dep[2])

  return redirect(url_for("admin_panel"))


@app.route("/admin/deposit/reject/<int:req_id>")
def admin_reject_deposit(req_id):
  if not session.get("admin"):
    return redirect(url_for("admin_login"))

  dep = get_deposit_request(req_id)
  if dep and dep[4] == "pending":
    update_deposit_status(req_id, "rejected")

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
