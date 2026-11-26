# LAB 4 — Traitement fiable en arrière-plan : Payments → Shipping (RabbitMQ)

**Module** : Microservice-oriented Architectures
**Professeur** : Zouheir BANOU
**Groupe** : Master Big Data & Data Science
**Scénario traité** : n° 2 — *Reliable background processing*
**Périmètre** : Payments (port 8085) et Shipping (port 8086) uniquement

Ce document complète `LAB4_analysis.md` (analyse, Q1–Q5) et
`LAB4_contracts.md` (contrats d'équipe). Il décrit l'implémentation.

---

## 1. Architecture mise en place

Le besoin : après un paiement réussi, la préparation de l'expédition doit être
déclenchée **sans faire attendre le client**, et **aucune demande ne doit être
perdue** si Shipping (ou le broker) est indisponible.

La difficulté n'est pas seulement de publier un message : c'est qu'un paiement
peut être enregistré en base **puis** le broker tomber avant la publication. Un
simple `publish()` après le `commit()` perdrait l'événement. La solution
retenue est le **transactional outbox**.

### Principe

1. Le client appelle `POST /api/payments` (endpoint REST inchangé).
2. Payments enregistre **dans une seule et même transaction** la ligne
   `payments` et la ligne `outbox_events`. Les deux sont écrites ensemble, ou
   aucune des deux.
3. Payments répond immédiatement au client (`201`). Rien dans le chemin HTTP
   ne contacte RabbitMQ : la réponse ne dépend ni du broker ni de Shipping.
4. Un **publieur en arrière-plan** (thread démon) lit les lignes `PENDING`,
   les publie dans une queue durable avec accusé de publication, puis les
   marque `PUBLISHED`.
5. Shipping consomme les messages, crée l'expédition, **puis seulement**
   acquitte le message.

### Diagramme du flux asynchrone

```
   Client
     │  POST /api/payments
     ▼
┌──────────────────────────────────────────────┐
│ PAYMENTS (8085)                              │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ UNE SEULE TRANSACTION SQLite           │  │
│  │   INSERT payments      (SUCCESS)       │  │
│  │   INSERT outbox_events (PENDING)       │  │
│  │   COMMIT                               │  │
│  └────────────────────────────────────────┘  │
│     │                                        │
│     └──► 201 Created ──────────────────────► Client  (~30 ms, broker ignoré)
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Thread « outbox-publisher »            │  │
│  │  - lit les lignes PENDING              │  │
│  │  - complète l'adresse via Orders       │  │
│  │  - publie (confirms + persistant)      │  │
│  │  - marque PUBLISHED                    │  │
│  │  - si broker KO : reste PENDING,       │  │
│  │    backoff 1s → 2s → 4s … 30s          │  │
│  └────────────────────────────────────────┘  │
└───────────────────│──────────────────────────┘
                    │  PaymentSucceeded (JSON, delivery_mode=2)
                    ▼
        ┌─────────────────────────────────┐
        │ RabbitMQ                        │
        │  queue « shipment.requests »    │
        │  durable, messages persistants  │
        │  x-dead-letter-exchange ────────┼──► shipment.dlx ──► shipment.requests.dlq
        └─────────────────│───────────────┘
                          │  (le message attend ici tant que Shipping est arrêté)
                          ▼
┌──────────────────────────────────────────────┐
│ SHIPPING (8086) — processus consommateur     │
│  prefetch = 1, ack manuel                    │
│                                              │
│  1. eventId déjà dans processed_events ?     │
│        oui → ack, on ne fait rien            │
│  2. expédition déjà créée pour l'orderId ?   │
│        oui → ack, on ne fait rien            │
│  3. adresse : message, sinon appel Orders    │
│  4. create_shipment()  (logique existante)   │
│  5. INSERT processed_events + COMMIT         │
│  6. ──► ACK (seulement maintenant)           │
│                                              │
│  échec temporaire → republié avec compteur   │
│  échec définitif / 5 tentatives → DLQ        │
└──────────────────────────────────────────────┘
                          │
                          ▼
                  table « shipments » (statut PREPARING)
```

L'API REST de Shipping continue de tourner dans un **processus séparé** : le
consommateur ne la touche pas.

---

## 2. Contrat du message

**Queue** : `shipment.requests` — durable, messages persistants
(`delivery_mode=2`), exchange par défaut, routing key = nom de la queue.
**Dead-letter** : `shipment.dlx` (fanout) → `shipment.requests.dlq`.

```json
{
  "eventId": "9b1c...-uuid",
  "eventType": "PaymentSucceeded",
  "type": "PaymentSucceeded",
  "paymentId": "64df...-uuid",
  "orderId": "order-123",
  "amount": 123.45,
  "method": "CARD",
  "occurredAt": "2026-11-25T23:24:33.493909+00:00",
  "address": { "name": "Hasnae ELMIR", "address": "12 Rue Al Andalous", "city": "Rabat" }
}
```

Le format est un **surensemble** : l'énoncé du LAB 4 demande `eventType`,
`paymentId`, `amount`, `method` ; le contrat d'équipe déjà fusionné (PR #8)
demandait `type` et `address`. Les deux champs `eventType` et `type` portent
toujours la même valeur, donc un consommateur écrit contre l'une ou l'autre
version fonctionne. Le tableau détaillé des champs est dans
`LAB4_contracts.md`, section 2.

**Aucune donnée sensible** n'est transportée : pas de numéro de carte, pas de
CVV, pas de jeton, pas d'identité du payeur. Un test automatisé le vérifie.

---

## 3. Décisions d'implémentation importantes

| Décision | Justification |
|---|---|
| **Transactional outbox** plutôt que publication directe | Sans outbox, un paiement peut être enregistré puis l'événement perdu si le broker tombe juste après le `commit()`. Ici l'événement est écrit dans la même transaction que le paiement : les deux existent ou aucun. |
| **Publication dans un thread de fond**, jamais dans la requête HTTP | Garantit que la réponse au client ne dépend ni de RabbitMQ ni de Shipping. Mesuré : 201 en ~32 ms avec le broker totalement absent. |
| **Adresse résolue par le publieur, pas par l'API** | Shipping exige `recipient_name`, `address`, `city` (NOT NULL) mais l'événement `PaymentSucceeded` ne les contient pas, et Payments ne stocke pas d'adresse : elle vit dans Orders. L'appel à Orders est fait par le thread de fond, donc il n'ajoute aucune latence pour le client. |
| **Double source pour l'adresse** | Payments l'ajoute quand Orders répond ; sinon Shipping la récupère lui-même au moment de consommer. Si aucune des deux voies n'aboutit, le message est **réessayé**, jamais transformé en expédition avec des données inventées. |
| **En-tête `X-Service-Key` vers Orders** | `get_caller()` d'Orders refuse un appel anonyme avec `401` quand `AUTH_MODE=remote` (la valeur par défaut). Les deux clients envoient donc le secret partagé `INTERNAL_API_KEY`, comme le fait déjà Orders vers ses propres dépendances. Vérifié en conditions réelles : sans l'en-tête `401 Authentication required`, avec l'en-tête `200`. |
| **Idempotence par `processed_events` (clé `eventId`)** + `UNIQUE(order_id)` | RabbitMQ garantit *at-least-once* : le même message peut arriver deux fois. La table d'idempotence attrape le doublon exact, la contrainte `UNIQUE` attrape le cas d'un événement republié avec un nouvel `eventId`. |
| **`ack` après le `commit`, jamais avant** | Si le consommateur meurt entre l'écriture et l'acquittement, RabbitMQ redonne le message : on peut traiter deux fois (c'est géré) mais jamais perdre. |
| **Distinction erreur temporaire / définitive** | Orders injoignable = temporaire → on réessaie. JSON illisible ou type d'événement inconnu = définitif → DLQ immédiate, sans boucler. |
| **Consommateur dans un processus séparé** | L'API REST de Shipping reste strictement inchangée et peut tourner sans le consommateur. |
| **`prefetch = 1`** | Un message à la fois : simple à raisonner pour un TP, et évite qu'un consommateur accapare la queue. |

### Ce que le système ne garantit pas

La livraison est **at-least-once avec traitement idempotent**, et non
*exactly-once*. L'exactly-once n'est pas atteignable ici : entre le `COMMIT` en
base et l'`ack` envoyé au broker il existe toujours une fenêtre où un crash
provoque une seconde livraison. C'est l'idempotence qui rend cette seconde
livraison inoffensive.

---

## 4. Fichiers créés et modifiés

### Payments

| Fichier | État | Rôle |
|---|---|---|
| `app/models/outbox.py` | créé | Table `outbox_events` |
| `app/events/contract.py` | créé | Construction de l'événement `PaymentSucceeded` |
| `app/events/publisher.py` | créé | Publication RabbitMQ (durable, persistant, confirms) |
| `app/events/outbox_worker.py` | créé | Thread de fond, vidage de l'outbox, backoff |
| `app/events/orders_client.py` | créé | Lecture best-effort de l'adresse auprès d'Orders |
| `app/services/payment_service.py` | modifié | Écrit la ligne outbox dans la transaction du paiement |
| `app/main.py` | modifié | Démarre/arrête le thread dans le `lifespan` |
| `app/routes/payments.py` | modifié | Ajout de `GET /api/payments/outbox` (lecture seule) |
| `app/config.py` | modifié | Configuration RabbitMQ et Orders par variables d'environnement |
| `schema.sql` | modifié | `CREATE TABLE outbox_events` |
| `requirements.txt`, `.env.example` | modifiés | `pika==1.3.2`, variables d'environnement |
| `tests/test_outbox.py` | créé | 12 tests |

### Shipping

| Fichier | État | Rôle |
|---|---|---|
| `app/models/processed_event.py` | créé | Table `processed_events` (idempotence) |
| `app/events/handler.py` | créé | Logique métier : événement → expédition |
| `app/events/consumer.py` | créé | Consommateur AMQP, ack/nack, DLQ, reconnexion |
| `app/events/orders_client.py` | créé | Récupération de l'adresse (repli) |
| `consumer_main.py` | créé | Point d'entrée du processus consommateur |
| `app/main.py` | modifié | Enregistrement du nouveau modèle |
| `app/config.py` | modifié | Configuration RabbitMQ et Orders |
| `schema.sql` | modifié | `CREATE TABLE processed_events` |
| `requirements.txt`, `.env.example` | modifiés | `pika==1.3.2`, variables d'environnement |
| `tests/test_consumer.py` | créé | 17 tests (sans broker) |
| `tests/test_integration_rabbitmq.py` | créé | 4 tests avec broker réel |

### En dehors de Payments et Shipping

**Aucun fichier.** Toutes les modifications sont contenues dans les dossiers
`payments/` et `shipping/`. Ni `docker-compose.yml`, ni les contrats d'équipe,
ni Orders, Inventory, Catalog, Auth ou Analytics n'ont été touchés. Aucun
endpoint REST existant n'a été modifié ni supprimé.

Le service `rabbitmq` utilisé ici est celui que l'équipe a déjà ajouté au
`docker-compose.yml` de la racine (PR #8 puis #12) : il est utilisé tel quel,
sans modification.

---

## 5. Résultats des tests

Lancement : `cd payments && python -m pytest tests/ -q` puis
`cd shipping && python -m pytest tests/ -q`.

```
payments : 25 passed
shipping : 33 passed, 4 skipped   (les 4 « skipped » = tests nécessitant un broker)
```

| # | Scénario demandé | Vérifié par | Résultat |
|---|---|---|---|
| 1 | Un paiement réussi déclenche un événement d'expédition | `test_successful_payment_records_outbox_event` | ✅ |
| 2 | Un paiement échoué ne déclenche aucun événement | `test_failed_payment_records_no_outbox_event` | ✅ |
| 3 | Le paiement réussit même si Shipping/RabbitMQ sont indisponibles | `test_payment_succeeds_when_broker_is_down` + mesure réelle (201 en 32 ms, broker absent) | ✅ |
| 4 | L'événement reste `PENDING` puis est publié au retour du broker | `test_publish_failure_leaves_event_pending`, `test_pending_event_is_published_when_broker_returns` | ✅ |
| 5 | Shipping consomme l'événement et crée l'expédition | `test_consuming_event_creates_shipment`, `test_consumer_acks_after_successful_commit` | ✅ (logique) / ⏭️ bout en bout : voir § 7 |
| 6 | Une livraison répétée ne crée pas de doublon | `test_same_event_delivered_twice_creates_one_shipment`, `test_different_event_id_same_order_creates_no_second_shipment` | ✅ |
| 7 | Un échec de traitement n'acquitte pas prématurément | `test_transient_failure_requeues_instead_of_acking`, `test_message_is_dead_lettered_after_max_attempts` | ✅ |
| 8 | Les endpoints REST existants fonctionnent toujours | `test_existing_rest_endpoints_still_work` (des deux côtés) + les 29 tests des LAB 2/3 inchangés | ✅ |

### Démonstration sur services réels (Payments 8085, Shipping 8086, Orders 8084)

Exécutée avec des bases de données jetables, **RabbitMQ volontairement absent**.

```
[3] POST /api/payments {"orderId":"DEMO-001","amount":249.99,"method":"CARD"}
      → HTTP 201 en 0.0517 s          (le broker n'est pas lancé)

[2] POST /api/payments {... "simulateFailure": true}
      → HTTP 201, status FAILED

[1+2] GET /api/payments/outbox
      → UN SEUL événement (le paiement échoué n'en a produit aucun) :
        {"eventId":"dcd4ef5f…","orderId":"DEMO-001","status":"PENDING",
         "attempts":1,"lastError":"Cannot connect to RabbitMQ: "}

[4] log : « RabbitMQ unavailable … Events stay pending, retrying in 1s »

    Enrichissement par le worker auprès d'Orders (code réel) :
      + "address": {"name":"Hasnae ELMIR","address":"12 Rue Al Andalous","city":"Rabat"}

[5] Consommation par Shipping  → {'status': 'CREATED', 'shipmentId': '7828eb51…'}
[6] Même événement redélivré   → {'status': 'DUPLICATE'}  — toujours 1 expédition
[6] Nouvel eventId, même order → {'status': 'DUPLICATE'}  — toujours 1 expédition

[8] GET /api/shipments/order/DEMO-001
      → {"trackingNumber":"MSOA-4YFMEPU2","status":"PREPARING", "address":{…}}
    PATCH status PREPARING → SHIPPED    : 200
    PATCH status SHIPPED  → DELIVERED   : 422 (transition refusée, règle inchangée)

[7] Événement sans adresse + Orders injoignable :
      « Transient failure (attempt 1/5), retrying: Orders unreachable: timed out »
      aucune expédition créée, message conservé pour réessai
```

L'événement n'est ni perdu ni publié à moitié : il attend, et le compteur de
tentatives progresse avec un backoff exponentiel. Seul le saut par le broker
lui-même n'a pas pu être exécuté (voir § 7, point 1).

---

## 6. Commandes pour tout lancer

```bash
# 1. Le broker (interface web : http://localhost:15672 — guest / guest)
docker compose up -d rabbitmq

# 2. Dépendances (une fois par service)
cd payments && pip install -r requirements.txt
cd ../shipping && pip install -r requirements.txt

# 3. L'API Payments (producteur)
cd payments && python -m uvicorn app.main:app --port 8085

# 4. L'API Shipping (inchangée)
cd shipping && python -m uvicorn app.main:app --port 8086

# 5. Le consommateur Shipping — dans un terminal séparé
cd shipping && python consumer_main.py

# 6. Orders, utile pour que l'adresse de livraison soit résolue
cd orders && python -m uvicorn app.main:app --port 8084
```

### Démonstration du scénario « Shipping indisponible »

```bash
# Consommateur arrêté, broker démarré
curl -X POST http://localhost:8085/api/payments \
  -H "Content-Type: application/json" \
  -d '{"orderId":"order-demo-1","amount":250,"method":"CARD"}'
# → 201 immédiat

curl http://localhost:8085/api/payments/outbox        # → PUBLISHED
# http://localhost:15672 → queue shipment.requests : 1 message en attente

python consumer_main.py                                # on démarre Shipping
curl http://localhost:8086/api/shipments/order/order-demo-1   # → l'expédition existe
```

### Démonstration du scénario « RabbitMQ indisponible »

```bash
docker compose stop rabbitmq
curl -X POST http://localhost:8085/api/payments \
  -H "Content-Type: application/json" \
  -d '{"orderId":"order-demo-2","amount":80,"method":"CASH"}'
# → 201 immédiat malgré le broker arrêté
curl http://localhost:8085/api/payments/outbox        # → PENDING, attempts qui montent

docker compose start rabbitmq
sleep 10
curl http://localhost:8085/api/payments/outbox        # → PUBLISHED
```

### Tests

```bash
cd payments && python -m pytest tests/ -v     # 25 tests, aucun broker requis
cd shipping && python -m pytest tests/ -v     # 33 tests + 4 ignorés sans broker

# Les 4 tests bout en bout, une fois RabbitMQ démarré :
docker compose up -d rabbitmq
cd shipping && python -m pytest tests/test_integration_rabbitmq.py -v
```

---

## 7. Limites connues et étapes manuelles

1. **Les 4 tests bout en bout n'ont pas pu être exécutés** sur la machine de
   développement : Docker n'y est pas installé, donc aucun RabbitMQ réel
   n'était joignable. Ils sont écrits et se *skippent* automatiquement en
   l'absence de broker. Les faire tourner demande `docker compose up -d
   rabbitmq` puis la commande ci-dessus. Tout le reste (58 tests) a réellement
   été exécuté et passe.
2. **La queue doit être créée par cette version du code.** Si une queue
   `shipment.requests` existe déjà sans l'argument `x-dead-letter-exchange`,
   RabbitMQ refusera la nouvelle déclaration (`PRECONDITION_FAILED`). Il faut
   alors la supprimer une fois depuis l'interface web (ou
   `rabbitmqctl delete_queue shipment.requests`) et la laisser se recréer.
3. **La DLQ ne se vide pas toute seule.** Les messages définitivement en échec
   s'accumulent dans `shipment.requests.dlq` et doivent être inspectés à la
   main depuis l'interface d'administration.
4. **Le publieur est un thread dans le processus de l'API.** C'est volontaire
   pour un TP : avec plusieurs instances de Payments, il faudrait un verrou
   (`SELECT … FOR UPDATE SKIP LOCKED`) pour qu'une seule instance publie une
   ligne donnée. SQLite ne le permet pas ; la table est néanmoins protégée par
   le fait que chaque ligne passe à `PUBLISHED` dans une transaction.
5. **Les lignes `PUBLISHED` ne sont jamais purgées.** Pour un TP c'est utile
   (elles servent de preuve), mais en production il faudrait les archiver.
6. **La production d'événements Kafka depuis Payments et Shipping**
   (`ecommerce.events`, pour Analytics) n'est pas couverte ici : l'énoncé de
   cette tâche limite le périmètre au scénario RabbitMQ. C'est une tâche
   distincte de `LAB4_analysis.md` (Q5).
7. **Le délai de reprise après un retour du broker** vaut au plus
   `OUTBOX_BACKOFF_MAX` (30 s par défaut), le temps que le backoff retombe.
   Réglable par variable d'environnement.
8. **Le contrat d'équipe `docs/lab4/LAB4_contracts.md` (section 2) n'a pas été
   modifié**, par choix de périmètre : rien n'a été touché en dehors de
   `payments/` et `shipping/`. Le message réellement émis est un
   **surensemble compatible** de celui qui y est décrit (il contient bien
   `eventId`, `type`, `orderId`, `address`, `occurredAt`, et ajoute
   `eventType`, `paymentId`, `amount`, `method`). Un consommateur écrit
   d'après le contrat actuel fonctionne donc sans changement, mais la section
   mériterait d'être complétée par la personne qui maintient ce document.
9. **Le conteneur RabbitMQ n'a pas de volume nommé** dans le
   `docker-compose.yml` de la racine (fichier non modifié, voir ci-dessus).
   La queue est bien déclarée *durable* et les messages sont *persistants* :
   ils survivent donc à un `docker compose restart rabbitmq`. En revanche un
   `docker compose down` supprime le conteneur et son stockage, donc les
   messages encore en file sont perdus. Pour une démonstration de durabilité
   complète, ajouter un volume au service `rabbitmq`.
