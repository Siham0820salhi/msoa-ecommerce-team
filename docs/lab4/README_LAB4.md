# LAB 4 : communication entre microservices

Équipe : SALHI Siham, ELMIR Hasnae, ESSADIKI Ibtissam, ABRABRI Zineb

## Documents

| Document | Contenu |
|---|---|
| `docs/lab4/LAB4_analysis.md` | Q1 à Q4 : analyse des besoins et décisions d'architecture |
| `docs/lab4/LAB4_contracts.md` | Contrats gRPC, RabbitMQ et Kafka |
| `proto/inventory.proto` | Contrat gRPC |
| `docker-compose.yml` | Infrastructure : RabbitMQ et Kafka |

## Décisions d'architecture

| Scénario | Mécanisme | Raison |
|---|---|---|
| Orders vers Inventory (appels fréquents, réponse immédiate) | gRPC | Synchrone, binaire, HTTP/2, contrat typé |
| Payments vers Shipping (traitement en arrière-plan, aucune perte) | RabbitMQ | File persistante et accusés de réception |
| Analytics (historique et replay) | Kafka | Journal durable, offsets par consommateur, rejeu |

Le reste reste en REST (frontend, Auth, Catalog, passage à `PAID`).

## Répartition du travail

| Membre | Partie | Dossier | Statut |
|---|---|---|---|
| Siham | Serveur gRPC (port 50051), contrats, Docker, analyse | `inventory/`, `proto/`, `docs/lab4/` | Terminé et testé |
| Zineb | Client gRPC dans Orders | `orders/` | à compléter |
| Hassnaa | RabbitMQ Payments vers Shipping | `payments/`, `shipping/` | à compléter |
| Ibtissam | Service Analytics (Kafka, port 8087) | `analytics/` | Terminé et testé |

## Lancement

1. `docker compose up -d` (RabbitMQ : http://localhost:15672, guest / guest ; Kafka : localhost:9092).
2. Lancer les services REST (Auth 8081, Catalog 8082, Inventory 8083, Orders 8084, Payments 8085, Shipping 8086), chacun depuis son dossier :
   `python -m uvicorn main:app --port <port> --reload`
3. Serveur gRPC d'Inventory : `cd inventory` puis `python grpc_server.py` (port 50051).
4. Analytics : `cd analytics` puis `python -m uvicorn main:app --port 8087 --reload`.
5. Frontend : `npm run dev`.

## Preuves de tests

| Mécanisme | Test | Capture |
|---|---|---|
| gRPC | Serveur lancé | `docs/tests/lab4/grpc-server.png` |
| gRPC | 6 appels : check, reserve, échec atomique, produit inconnu, release | `docs/tests/lab4/grpc-client-test.png` |
| gRPC | Stock inchangé après l'échec (via REST) | `docs/tests/lab4/grpc-atomicity-rest.png` |
| RabbitMQ | Interface en ligne | `docs/tests/lab4/rabbitmq-up.png` |
| Kafka | 9 événements publiés pendant qu'Analytics est arrêté | `docs/tests/lab4/analytics-producer-while-stopped.png` |
| Kafka | Analytics redémarré rattrape l'historique (27 événements) | `docs/tests/lab4/analytics-late-consumer.png` |
| Kafka | Replay : 18 événements rejoués depuis le journal | `docs/tests/lab4/analytics-replay.png` |
| Analytics (autre série) | health, events, summary, replay | `docs/contract/tests/` |

## Ce qui reste en REST

Frontend vers tous les services, Orders vers Auth et Catalog, Payments vers Orders (passage à `PAID`), Orders vers Shipping (consultation avant annulation). Les endpoints REST d'Inventory restent actifs.

## Limites connues

- Un seul broker Kafka et un seul nœud RabbitMQ (pas de réplication), suffisant pour un TP.
- Les bases SQLite ne conviendraient pas à la production.
- Kafka est indisponible : les services producteurs continuent de fonctionner et journalisent l'erreur.