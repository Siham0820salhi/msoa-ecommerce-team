# Contrat d'API : Analytics

Responsable : Ibtissam Essadiki
Analytics : http://localhost:8087
Broker Kafka : localhost:9092 | Topic : `ecommerce.events` | Consumer Group : `analytics`
Conventions communes (headers, schéma d'erreur, codes HTTP) : voir `00_conventions.md`.

---

# ANALYTICS (port 8087)

Propriétaire des tables `events`, `shipments` et `stats` dans `analytics.db`.
Service de lecture analytique et de relecture d'événements Kafka (Event Retention & Replay).
Chaque événement est dédupliqué grâce à son identifiant unique `eventId`.

## Contrat d'événements Kafka (`topic: ecommerce.events`)

Format JSON consommé :

```json
{
  "eventId": "string (UUID, requis pour la déduplication)",
  "eventType": "OrderCreated | OrderCancelled | PaymentSucceeded | ShipmentStatusUpdated | UserRegistered",
  "timestamp": "string (ISO 8601 UTC)",
  "payload": {
    "orderId": "string",
    "total": "number",
    "amount": "number",
    "shipmentId": "string",
    "status": "PREPARING | SHIPPED | IN_TRANSIT | DELIVERED"
  }
}
```

---

## GET /api/analytics/summary

Description : retourne les statistiques globales calculées à partir des événements consommés.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` ->
  ```json
  {
    "totalOrders": 3,
    "cancelledOrders": 1,
    "totalRevenue": 9098.0,
    "shipmentsByStatus": {
      "DELIVERED": 1,
      "SHIPPED": 1
    },
    "eventsByType": {
      "OrderCreated": 3,
      "PaymentSucceeded": 2,
      "ShipmentStatusUpdated": 3,
      "OrderCancelled": 1
    },
    "totalEvents": 9,
    "lastUpdated": "2026-11-25T19:14:31Z"
  }
  ```
- Erreurs :
  - `500` -> `{ "message": "Internal server error" }`

## GET /api/analytics/events

Description : retourne la liste de tous les événements uniques reçus et stockés dans `analytics.db` (du plus récent au plus ancien).
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` ->
  ```json
  [
    {
      "eventId": "25cb50dd-b839-4819-ae22-1e33a5c4206a",
      "eventType": "OrderCancelled",
      "timestamp": "2026-11-25T19:13:24Z",
      "payload": {
        "orderId": "order-103",
        "userId": "user-2",
        "reason": "Customer cancelled"
      },
      "receivedAt": "2026-11-25T19:14:31Z"
    }
  ]
  ```
- Erreurs :
  - `500` -> `{ "message": "Internal server error" }`

## POST /api/analytics/replay

Description : vide les statistiques et la table `events`, puis relit tout l'historique du topic `ecommerce.events` depuis l'offset `earliest` (`0`) afin de recalculer les métriques à l'identique.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` ->
  ```json
  {
    "success": true,
    "replayedEvents": 9,
    "summary": {
      "totalOrders": 3,
      "cancelledOrders": 1,
      "totalRevenue": 9098.0,
      "shipmentsByStatus": {
        "DELIVERED": 1,
        "SHIPPED": 1
      },
      "eventsByType": {
        "OrderCreated": 3,
        "PaymentSucceeded": 2,
        "ShipmentStatusUpdated": 3,
        "OrderCancelled": 1
      },
      "totalEvents": 9,
      "lastUpdated": "2026-11-25T19:19:59Z"
    }
  }
  ```
- Erreurs :
  - `503` -> `{ "message": "Kafka broker unavailable: ..." }`
  - `500` -> `{ "message": "Internal server error" }`

## GET /health

Description : indique l'état du service.
- URL Params : aucun
- Data Params : aucun
- Headers : `Accept: application/json`
- Body : aucun
- Succès : `200` -> `{ "service": "analytics", "status": "UP" }`

---

# Interactions (Analytics)

| Fournisseur | Consommateur | Information échangée |
|---|---|---|
| Orders / Payments / Shipping (via Kafka `ecommerce.events`) | Analytics | Événements métier asynchrones (`OrderCreated`, `OrderCancelled`, `PaymentSucceeded`, `ShipmentStatusUpdated`) avec rétention et replay |
| Analytics | Administrateur / Frontend | Consultation des métriques (`GET /api/analytics/summary`), historique (`GET /api/analytics/events`) et replay (`POST /api/analytics/replay`) |

Analytics ne modifie aucun autre service et n'expose que des APIs de consultation et de replay.