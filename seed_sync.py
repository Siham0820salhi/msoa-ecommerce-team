"""Synchronise catalog.db et inventory.db avec src/data/products.js"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent

PRODUCTS = [
    (1, "Lenovo ThinkPad E14", "Laptops", 8499, "https://placehold.co/600x400?text=ThinkPad+E14",
     "Reliable 14-inch business laptop with Intel Core i5, 16GB RAM and 512GB SSD.", 12),
    (2, "Samsung Galaxy A55", "Smartphones", 4299, "https://placehold.co/600x400?text=Galaxy+A55",
     "5G smartphone with a 6.6-inch AMOLED display and 128GB storage.", 20),
    (3, "Sony WH-1000XM5", "Audio", 3499, "https://placehold.co/600x400?text=Sony+Headphones",
     "Wireless noise-cancelling headphones with premium sound.", 8),
    (4, "Logitech MX Master 3S", "Accessories", 1199, "https://placehold.co/600x400?text=MX+Master+3S",
     "Ergonomic wireless mouse designed for productivity.", 25),
    (5, "Dell UltraSharp 27", "Monitors", 3999, "https://placehold.co/600x400?text=Dell+Monitor",
     "27-inch QHD monitor with excellent color accuracy.", 10),
    (6, "Apple iPad Air", "Tablets", 7299, "https://placehold.co/600x400?text=iPad+Air",
     "Powerful and lightweight tablet for work and entertainment.", 15),
]

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Catalog : uniquement catalog.db ---
conn = sqlite3.connect(ROOT / "catalog" / "catalog.db")
conn.execute("DELETE FROM products")
conn.executemany(
    "INSERT INTO products (id, name, category, price, image, description) VALUES (?,?,?,?,?,?)",
    [p[:6] for p in PRODUCTS],
)
conn.commit()
conn.close()

# --- Inventory : uniquement inventory.db ---
conn = sqlite3.connect(ROOT / "inventory" / "inventory.db")
conn.execute("DELETE FROM stock")
conn.executemany(
    "INSERT INTO stock (product_id, quantity, updated_at) VALUES (?,?,?)",
    [(p[0], p[6], now) for p in PRODUCTS],
)
conn.commit()
conn.close()

print("OK : catalog.db et inventory.db synchronises avec products.js")