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

  # Fiyat sorgulama adımı
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

    max_price = 500.0
    country_data = price_res.get(str(service["country"]), {})
    for op_name, op_info in country_data.items():
      if "cost" in op_info:
        max_price = float(op_info["cost"])
        break
  except Exception as e:
    print("Fiyat API Hatası:", str(e))
    max_price = 500.0

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
      from flask import flash

      flash(
          f"API'den hata döndü: {num_res.get('message', 'Bilinmeyen hata')}",
          "error",
      )
      return redirect(url_for("index"))
  except Exception as e:
    from flask import flash

    flash(f"API Çözümleme Hatası: {str(e)}", "error")
    return redirect(url_for("index"))
