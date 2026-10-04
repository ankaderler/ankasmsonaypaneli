import sqlite3

DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Kullanıcılar tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  # Bakiye yükleme talepleri tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  # Satın alım / siparişler tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_key TEXT,
            price REAL,
            phone TEXT,
            activation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  conn.commit()
  conn.close()


def add_user(username, password):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, password),
    )
    conn.commit()
    success = True
  except sqlite3.IntegrityError:
    success = False
  conn.close()
  return success


def get_user_by_credentials(username, password):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, username, balance FROM users WHERE username = ? AND"
      " password = ?",
      (username, password),
  )
  user = cursor.fetchone()
  conn.close()
  return user


def get_user_by_id(user_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, username, balance FROM users WHERE user_id = ?",
      (user_id,),
  )
  user = cursor.fetchone()
  conn.close()
  return user


def update_user_balance(user_id, amount):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET balance = balance + ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()
  conn.close()


def set_user_balance_manual(user_id, amount):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id)
  )
  conn.commit()
  conn.close()


def create_deposit_request(user_id, amount):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO deposit_requests (user_id, amount) VALUES (?, ?)",
      (user_id, amount),
  )
  req_id = cursor.lastrowid
  conn.commit()
  conn.close()
  return req_id


def get_deposit_request(req_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, user_id, amount, status FROM deposit_requests WHERE id = ?",
      (req_id,),
  )
  row = cursor.fetchone()
  conn.close()
  return row


def update_deposit_status(req_id, status):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE deposit_requests SET status = ? WHERE id = ?", (req_id, status)
  )
  # Yukarıdaki sorguda sıra hatasını önlemek için düzeltme:
  cursor.execute(
      "UPDATE deposit_requests SET status = ? WHERE id = ?", (status, req_id)
  )
  conn.commit()
  conn.close()


def create_order_db(user_id, service_key, price, phone, activation_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO orders (user_id, service_key, price, phone, activation_id)"
      " VALUES (?, ?, ?, ?, ?)",
      (user_id, service_key, price, phone, activation_id),
  )
  conn.commit()
  conn.close()


def get_all_users():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, username, balance, created_at FROM users ORDER BY"
      " user_id DESC"
  )
  rows = cursor.fetchall()
  conn.close()
  return rows


def get_all_deposits():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      """
        SELECT d.id, u.username, d.amount, d.status, d.created_at, d.user_id 
        FROM deposit_requests d 
        JOIN users u ON d.user_id = u.user_id 
        ORDER BY d.id DESC
    """
  )
  rows = cursor.fetchall()
  conn.close()
  return rows


def get_all_orders():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      """
        SELECT o.order_id, u.username, o.service_key, o.price, o.phone, o.activation_id, o.created_at 
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        ORDER BY o.order_id DESC
    """
  )
  rows = cursor.fetchall()
  conn.close()
  return rows
