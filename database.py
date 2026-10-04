import sqlite3

DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_key TEXT,
            price REAL,
            status TEXT DEFAULT 'pending_payment'
        )
    """)

  conn.commit()
  conn.close()


def register_user(user_id, username):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
      (user_id, username),
  )
  conn.commit()
  conn.close()


def create_order(user_id, service_key, price):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO orders (user_id, service_key, price, status) VALUES (?, ?,"
      " ?, 'pending_payment')",
      (user_id, service_key, price),
  )
  order_id = cursor.lastrowid
  conn.commit()
  conn.close()
  return order_id


def get_order(order_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT user_id, service_key, price, status FROM orders WHERE order_id ="
      " ?",
      (order_id,),
  )
  row = cursor.fetchone()
  conn.close()
  return row


def update_order_status(order_id, status):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id)
  )
  conn.commit()
  conn.close()
