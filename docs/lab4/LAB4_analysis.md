# LAB 4 : analyse et décisions d'architecture

Équipe : SALHI Siham, ELMIR Hassnaa, ESSADIKI Ibtissam, ABRABRI Zineb

## Partie I : analyse des besoins

### Q1. Communication haute performance (Orders et Inventory)

**a. Orders a-t-il besoin d'une réponse immédiate ?** Oui. Orders ne peut pas créer la commande avant de savoir si le stock est disponible et réservé. La communication doit rester **synchrone** (requête-réponse).

**b. Limites de REST pour des appels fréquents et rapides :**
- JSON en texte : verbeux, coûteux à encoder et à décoder.
- HTTP/1.1 : une requête à la fois par connexion, en-têtes répétés.
- Pas de contrat strict : les erreurs de format ne sont détectées qu'à l'exécution.
- La latence et la charge CPU augmentent avec le nombre de transactions.

**c. Caractéristiques d'une alternative :**
- Format binaire compact (Protocol Buffers).
- HTTP/2 : connexions persistantes et multiplexage.
- Contrat typé défini à l'avance (fichier `.proto`), code client et serveur généré.
- Modèle requête-réponse conservé, donc synchrone.

### Q2. Traitement fiable en arrière-plan (Payments vers Shipping)

**a. Payments doit-il attendre la préparation de l'expédition ?** Non. Le client doit recevoir sa confirmation de paiement sans attendre. La préparation peut se faire plus tard.

**b. Si Shipping est indisponible au moment du paiement :** avec un appel REST synchrone, l'appel échoue. Soit le paiement est annulé à tort, soit la demande d'expédition est perdue et la commande n'est jamais expédiée.

**c. Comment préserver les demandes :** placer la demande dans un **broker de messages** avec une **file persistante**. Payments publie le message puis répond au client. Le message reste en file jusqu'à ce que Shipping le traite et envoie un accusé de réception (`ack`). C'est un découplage temporel : producteur et consommateur n'ont pas besoin d'être disponibles en même temps.

### Q3. Rétention et rejeu des événements (Analytics)

**a. Pourquoi Analytics a besoin d'événements passés :** il calcule des statistiques sur tout l'historique (commandes, paiements, expéditions). Un service déployé tard ou en panne doit pouvoir rattraper ce qu'il a manqué.

**b. Limites si les événements sont livrés puis supprimés :**
- Les événements manqués sont perdus définitivement.
- Impossible de recalculer un état ou de corriger une erreur en rejouant.
- Un nouveau consommateur n'a aucun historique.
- Chaque nouveau besoin oblige à modifier les producteurs.

**c. Capacités nécessaires :**
- Stockage durable des événements dans un journal (log).
- Rétention configurable.
- Plusieurs consommateurs indépendants, chacun avec son propre offset (position de lecture).
- Relecture depuis le début (replay).
- Ordre garanti au sein d'une partition.

## Partie II : décisions d'architecture (Q4)

| Scénario | Choix | Justification | Alternatives écartées |
|---|---|---|---|
| 1. Orders vers Inventory | **gRPC** | Synchrone, format binaire, HTTP/2, contrat typé et code généré | REST : trop verbeux et lent pour des appels fréquents. File de messages : asynchrone, or Orders attend la réponse |
| 2. Payments vers Shipping | **RabbitMQ** | File persistante, accusés de réception, livraison différée si Shipping est arrêté, simple pour une tâche à traiter une fois | REST et gRPC : synchrones, la demande est perdue si Shipping est indisponible. Kafka : possible mais plus lourd, et l'historique n'est pas nécessaire ici |
| 3. Analytics | **Kafka** | Journal durable, rétention, un offset par consommateur, replay | RabbitMQ : le message est supprimé après consommation, donc pas de replay. REST : ne conserve aucun historique |

**Principe retenu :** RabbitMQ distribue des **tâches** (le message disparaît après traitement). Kafka conserve un **historique** (les messages restent et peuvent être relus).

**Ce qui reste en REST :** frontend vers services, Orders vers Auth et Catalog, Payments vers Orders (le passage à `PAID` doit être immédiat). REST reste approprié pour ces interactions simples, et l'existant n'est pas cassé.

## Partie II : implémentation (Q5)

| Mécanisme | Services | Responsable | Contrat |
|---|---|---|---|
| gRPC | Inventory (serveur, port 50051), Orders (client) | Siham, Zineb | `proto/inventory.proto` |
| RabbitMQ | Payments (producteur), Shipping (consommateur) | Hassnaa | `LAB4_contracts.md`, section 2 |
| Kafka | Orders, Payments, Shipping (producteurs), Analytics (consommateur) | Ibtissam, Zineb, Hassnaa | `LAB4_contracts.md`, section 3 |

Preuves de tests : `docs/tests/lab4/`.