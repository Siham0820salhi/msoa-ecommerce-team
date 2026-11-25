# LAB 4 : contrats de communication

## 1. gRPC : Orders (client) vers Inventory (serveur)

- Fichier : `proto/inventory.proto`
- Serveur : Inventory, port **50051**
- Client : Orders
- Les endpoints REST d'Inventory restent actifs (le frontend les utilise).

| RPC | Requête | Réponse | Erreurs gRPC |
|---|---|---|---|
| CheckStock | `ItemsRequest` | `CheckResponse { available }` | `INVALID_ARGUMENT` |
| ReserveStock | `ItemsRequest` | `ReserveResponse { success, message }` | `INVALID_ARGUMENT`, `NOT_FOUND`, `FAILED_PRECONDITION` |
| ReleaseStock | `ItemsRequest` | `ReserveResponse { success, message }` | `INVALID_ARGUMENT`, `NOT_FOUND` |

Correspondance avec les codes REST, à appliquer dans Orders :

| Code gRPC | Code REST renvoyé par Orders |
|---|---|
| `INVALID_ARGUMENT` | 400 |
| `NOT_FOUND` | 404 |
| `FAILED_PRECONDITION` (stock insuffisant) | 409 |
| `UNAVAILABLE` (service arrêté) | 503 |

## 2. RabbitMQ : Payments (producteur) vers Shipping (consommateur)

- Broker : `localhost:5672` (interface web : http://localhost:15672, guest / guest)
- Queue : `shipment.requests` (**durable**, messages **persistants**)
- Acquittement (`ack`) envoyé par Shipping **après** l'enregistrement en base
- Idempotence : un message en double pour le même `orderId` est ignoré (`order_id` est `UNIQUE`)

Message :

```json
{
  "eventId": "uuid",
  "type": "PaymentSucceeded",
  "orderId": "order-123",
  "address": { "name": "string", "address": "string", "city": "string" },
  "occurredAt": "2026-11-25T10:00:00Z"
}
```

## 3. Kafka : tous les services (producteurs) vers Analytics (consommateur)

- Broker : `localhost:9092`
- Topic : `ecommerce.events`
- Clé du message : `orderId` (garantit l'ordre des événements d'une même commande)
- Consumer group d'Analytics : `analytics`
- Rétention : conservée (permet le replay)

Schéma d'événement :

```json
{
  "eventId": "uuid",
  "type": "OrderCreated | OrderCancelled | PaymentSucceeded | ShipmentStatusChanged",
  "source": "orders | payments | shipping",
  "orderId": "order-123",
  "payload": {},
  "occurredAt": "2026-11-25T10:00:00Z"
}
```

| Type | Producteur | Contenu de `payload` |
|---|---|---|
| OrderCreated | Orders | `{ "userId", "total", "items": [...] }` |
| OrderCancelled | Orders | `{ "userId", "total" }` |
| PaymentSucceeded | Payments | `{ "amount", "method" }` |
| ShipmentStatusChanged | Shipping | `{ "status", "trackingNumber" }` |

Règle : si Kafka est indisponible, le service producteur continue de fonctionner (il journalise l'erreur).

## 4. Ce qui reste en REST

Frontend vers tous les services, Orders vers Auth, Orders vers Catalog, Payments vers Orders (passage à `PAID`), Orders vers Shipping (consultation avant annulation).