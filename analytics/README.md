# Analytics Service

Service d'analyse métier asynchrone (Event Streaming) pour l'application MSOA E-commerce (LAB 4).

- **Responsable :** ESSADIKI Ibtissam
- **Port :** `8087`
- **Base de données :** `analytics.db` (SQLite)
- **Broker Kafka :** `localhost:9092` | **Topic :** `ecommerce.events` | **Consumer Group :** `analytics`

## Architecture & Fonctionnement

- Consomme les événements métier publiés sur le topic Kafka `ecommerce.events` (`auto.offset.reset = earliest`).
- Stocke chaque événement dans la table `events` de `analytics.db` avec **déduplication par `eventId`** (`INSERT OR IGNORE`).
- Maintient en temps réel les statistiques globales : nombre de commandes, annulations, chiffre d'affaires, expéditions par statut.
- Supporte le **replay complet** depuis le début du journal Kafka (`POST /api/analytics/replay`).

## Installation & Lancement

### 1. Démarrer Kafka (Docker)
```powershell
cd analytics
docker compose up -d
```

### 2. Installer les dépendances & lancer le service
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8087
```

Swagger UI : `http://localhost:8087/docs`

## Endpoints REST

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/health` | Statut du service (`{"service": "analytics", "status": "UP"}`) |
| GET | `/api/analytics/summary` | Statistiques globales (commandes, annulations, CA, expéditions) |
| GET | `/api/analytics/events` | Liste des événements uniques reçus |
| POST | `/api/analytics/replay` | Réinitialise les stats et relit tout l'historique Kafka depuis l'offset 0 |

## Exemples curl

```bash
curl http://localhost:8087/health
curl http://localhost:8087/api/analytics/summary
curl http://localhost:8087/api/analytics/events
curl -X POST http://localhost:8087/api/analytics/replay
```

## Scénario de test (Retention & Replay)

1. Publier des événements avant le démarrage d'Analytics : `python test_producer.py` (9 événements publiés sur `ecommerce.events`).
2. Démarrer Analytics après la publication (`python -m uvicorn main:app --reload --port 8087`).
3. Vérifier `GET /api/analytics/summary` -> `totalOrders: 3`, `cancelledOrders: 1`, `totalRevenue: 9098`, `shipmentsByStatus: {"DELIVERED": 1, "SHIPPED": 1}`, `totalEvents: 9`.
4. Lancer `POST /api/analytics/replay` -> `replayedEvents: 9` et les mêmes statistiques sont recalculées à l'identique.