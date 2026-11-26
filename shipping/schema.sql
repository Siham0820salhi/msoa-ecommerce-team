PRAGMA foreign_keys = ON;
CREATE TABLE shipments (id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, recipient_name TEXT NOT NULL, address TEXT NOT NULL, city TEXT NOT NULL, tracking_number TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK(status IN ('PREPARING','SHIPPED','IN_TRANSIT','DELIVERED','CANCELLED')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE processed_events (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, order_id TEXT NOT NULL, shipment_id TEXT, processed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_processed_events_order ON processed_events(order_id);
