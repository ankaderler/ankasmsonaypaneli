import sqlite3

DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            service_key TEXT,
            price REAL,
            status TEXT DEFAULT 'pending_payment',
            phone TEXT DEFAULT '',
            activation_id TEXT DEFAULT ''
        )
    """)
  conn.commit()
  conn.close()


def create_order(customer_name, service_key, price):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO orders (customer_name, service_key, price, status) VALUES"
      " (?, ?, ?, 'pending_payment')",
      (customer_name, service_key, price),
  )
  order_id = cursor.lastrowid
  conn.commit()
  conn.close()
  return order_id


def get_order(order_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT customer_name, service_key, price, status, phone, activation_id"
      " FROM orders WHERE order_id = ?",
      (order_id,),
  )
  row = cursor.fetchone()
  conn.close()
  return row


def get_all_orders():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT order_id, customer_name, service_key, price, status, phone,"
      " activation_id FROM orders ORDER BY order_id DESC"
  )
  rows = cursor.fetchall()
  conn.close()
  return rows


def update_order_complete(order_id, phone, activation_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE orders SET status = 'completed', phone = ?, activation_id = ? "
      "WHERE order_id = ?",
      (phone, activation_id, order_id),
  )
  conn.commit()
  conn.close()


def update_order_status(order_id, status):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id)
  )
  conn.commit()
  conn.close()
