# LAB 4 — Contribution Zineb / Orders

Branche cible : `feature/lab4-orders`.

## Analyse et justification
- gRPC pour la réservation et la restitution : appel synchrone typé, réponse immédiate nécessaire avant de valider la commande. Protobuf et HTTP/2 réduisent le coût de sérialisation et définissent un contrat partagé.
- Kafka pour Analytics : découplage du traitement analytique, historique et replay, partitionnement par clé orderId. La publication intervient après la validation en base. Les autres échanges REST sont conservés.
- RabbitMQ relève de Hassnaa ; serveur Inventory de Siham ; consommateur Analytics d'Ibtissam.

## Résultats réellement exécutés
Voir `orders-pytest.txt` : 48 tests réussis. Le test gRPC utilise un vrai serveur gRPC local de test avec stock simulé, et non le serveur de Siham. Il vérifie création 201, stock 10 → 8, refus 409, annulation 200, stock 8 → 10, deuxième annulation 409 et un seul appel de restitution. Un autre test arrête le serveur et vérifie 503. Les événements sont vérifiés via une publication simulée ; une panne du producteur est simulée et journalisée.

## Restant à valider sur le dépôt du groupe
- Intégration avec le vrai serveur Inventory de Siham.
- Kafka réel et consommation par Analytics, captures du broker et des réponses API.
- Accord sur les alias JSON (contrat Git et message Analytics divergent).
- Installation complète des dépendances : réseau indisponible dans l'environnement de préparation ; grpcio-tools et kafka-python n'ont pas pu être installés. Le client gRPC et les tests ont fonctionné avec les bibliothèques déjà présentes.
- Aucun commit ni PR distant réalisé : l'archive fournie ne contient pas de dépôt .git.

Le protocole partagé ne contient pas de clé d'idempotence pour les mutations Inventory : la protection existante contre la double annulation normale est conservée, mais une panne après application distante et avant réponse peut rendre le résultat ambigu.
