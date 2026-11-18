# API Evolution — Breaking Change Analysis

**Module**: MSOA — LAB 3 · PART III  
**Author**: Hasnae ELMIR  

---

## Q4 — Why the Price Change Breaks Consumers

### The breaking change

The Catalog service evolves the `price` field of a product from a **flat number** to a **structured object**:

**Before (v1)**:
```json
{
  "id": 12,
  "name": "Lenovo ThinkPad E14",
  "price": 8499
}
```

**After (v2 — breaking)**:
```json
{
  "id": 12,
  "name": "Lenovo ThinkPad E14",
  "price": {
    "amount": 8499,
    "currency": "MAD"
  }
}
```

### Why this breaks existing consumers

| Consumer | How it uses `price` | Impact |
|---|---|---|
| **React frontend** (`Cart.jsx`) | `item.price * item.quantity` | `{...} * 2` → `NaN` — cart total becomes `NaN` |
| **React frontend** (`Checkout.jsx`) | Passes `price` as `amount` to Payments | Sends an object instead of a number → Payments rejects with 422 |
| **React frontend** (`Products.jsx`) | Displays `{product.price} MAD` | Renders `[object Object] MAD` |
| **Orders service** | `unitPrice = product.price` stored in `order_items` | Stores `"[object Object]"` instead of `8499` → total calculation is wrong |
| **Payments service** | Receives `amount` from Orders | If Orders passes `NaN` or `"[object Object]"`, Payments validation fails |

### Root cause

The change is **structurally incompatible**: consumers that perform arithmetic or display the value directly cannot handle an object where a scalar is expected. This is a **breaking type change** — the most dangerous category of API evolution.

---

## Q5 — Strategies to Avoid Breaking Consumers

Three strategies can preserve backward compatibility:

### Strategy 1 — Additive field (recommended)

Keep the original `price` field unchanged and **add** a new `pricing` object alongside it.

```json
{
  "id": 12,
  "name": "Lenovo ThinkPad E14",
  "price": 8499,
  "pricing": {
    "amount": 8499,
    "currency": "MAD"
  }
}
```

✅ **Pros**: Zero breaking change — all existing consumers continue to work. New consumers can adopt `pricing` at their own pace.  
❌ **Cons**: Data redundancy; both fields must stay in sync.

**When to use**: The preferred approach for all non-critical evolutions. Compatible with the team's principle of *progressive service integration*.

---

### Strategy 2 — URL versioning

Publish the new structure under a versioned path and keep the old path unchanged:

```
GET /api/v1/products/{id}  →  { "price": 8499 }
GET /api/v2/products/{id}  →  { "price": { "amount": 8499, "currency": "MAD" } }
```

✅ **Pros**: Contracts are explicit and self-documenting. Each consumer migrates independently.  
❌ **Cons**: Routing duplication; the Catalog service must maintain two code paths indefinitely until all consumers migrate.

**When to use**: When the new structure is fundamentally different and the migration must be coordinated across all teams (e.g., a major release cycle).

---

### Strategy 3 — Content negotiation

The same endpoint returns different representations based on the `Accept` header:

```
GET /api/products/12
Accept: application/json              → { "price": 8499 }

GET /api/products/12
Accept: application/vnd.msoa.v2+json → { "price": {...} }
```

✅ **Pros**: Single URL, no routing duplication.  
❌ **Cons**: Complex to implement and test; most HTTP clients (including React's `fetch`) send generic `Accept: */*`, which makes defaulting tricky and error-prone.

**When to use**: When URL pollution must be avoided and the team has strong API-Gateway support (e.g., behind Kong or AWS API Gateway with header-based routing).

---

### Comparison table

| Criterion | Additive field | URL versioning | Content negotiation |
|---|---|---|---|
| Breaking change | None | None | None |
| Implementation effort | Low | Medium | High |
| Consumer migration effort | None | Medium | Medium |
| Discoverability (OpenAPI) | Good | Excellent | Poor |
| Recommended for this project | ✅ **Yes** | Optional | No |

---

## Q6 — Chosen Strategy and Implementation

### Decision: Additive field

We choose the **additive field** strategy because:

1. The team is working in parallel on independent services — a URL-versioned migration would require coordinated changes across all six teams simultaneously.
2. The React frontend was built to call a single endpoint per resource; changing URL paths would require modifying service layer files (`catalogService.js`), which the lab instructions prohibit for Payments/Shipping owners.
3. The additive approach requires zero changes on the consumer side, satisfying the fundamental rule: *"Microservices developed independently must still communicate reliably."*

### Implementation

#### Catalog service — `GET /api/products/{id}` (after evolution)

```json
{
  "id": 12,
  "name": "Lenovo ThinkPad E14",
  "description": "Intel Core i5, 8 GB RAM, 256 GB SSD",
  "price": 8499,
  "pricing": {
    "amount": 8499,
    "currency": "MAD"
  },
  "stock": 15,
  "category": "laptops"
}
```

- `price` (number) — **kept** for all existing consumers
- `pricing` (object) — **added** for future consumers that need currency-aware display

#### Catalog schema evolution (SQLite)

```sql
-- No schema change needed: price remains a REAL column
-- pricing is computed at the application layer
ALTER TABLE products ADD COLUMN currency TEXT NOT NULL DEFAULT 'MAD';
```

The FastAPI/Flask response layer builds `pricing` dynamically:

```python
# catalog/main.py — response serialisation
def product_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "price": p.price,           # kept for backward compatibility
        "pricing": {
            "amount": p.price,
            "currency": p.currency or "MAD"
        },
        "stock": p.stock,
        "category": p.category,
    }
```

#### Deprecation notice (optional, non-breaking)

Add a response header to signal that `price` (flat) is soft-deprecated:

```
Deprecation: true
Sunset: 2027-06-01
Link: </api/products/{id}>; rel="deprecation"
```

Consumers that read this header can plan their migration to `pricing.amount` before the sunset date.

### Migration path for consumers

| Consumer | Current code | Action needed |
|---|---|---|
| React `Cart.jsx` | `item.price * qty` | No change (still works) |
| React `Products.jsx` | `{product.price} MAD` | No change (still works) |
| React `Checkout.jsx` | `amount: product.price` | No change (still works) |
| Orders service | `unitPrice = product.price` | No change (still works) |
| Future consumer (e.g., invoice PDF) | — | Use `product.pricing.amount` and `product.pricing.currency` |

**Zero services need to be modified.** The additive field achieves full backward compatibility.
