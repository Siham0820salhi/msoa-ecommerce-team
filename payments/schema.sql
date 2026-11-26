PRAGMA foreign_keys = ON;
CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, amount REAL NOT NULL CHECK(amount >= 0), method TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')), created_at TEXT NOT NULL);
CREATE TABLE outbox_events (id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','PUBLISHED','FAILED')), attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, created_at TEXT NOT NULL, published_at TEXT);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox_events(status);
