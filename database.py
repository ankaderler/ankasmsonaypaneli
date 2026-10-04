import sqlite3

DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    """)

  # Bekleyen ödeme / dekont bildirimleri
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS activations (
            activation_id TEXT PRIMARY KEY,
            user_id INTEGER,
            phone_number TEXT,
            service_key TEXT
        )
    """)

  conn.commit()
  conn.close()


def get_user_balance(user_id):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if not row:
    cursor.execute(
        "INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0.0)
    )
    conn.commit()
    balance = 0.0
  else:
    balance = row[0]
  conn.close()
  return balance


def update_user_balance(user_id, amount):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if not row:
    cursor.execute(
        "INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount)
    )
  else:
    new_balance = row[0] + amount
    cursor.execute(
        "UPDATE users SET balance = ? WHERE user_id = ?",
        (new_balance, user_id),
    )
  conn.commit()
  conn.close()
