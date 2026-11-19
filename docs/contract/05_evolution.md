# Partie III : évolution de l'API et breaking changes

## Q4. Pourquoi le changement casse les consommateurs

Le JSON reste syntaxiquement valide, mais le **contrat** a changé : le type de `price` passe de `number` à `object`. Un consommateur écrit pour un nombre échoue.

| Composant | Conséquence |
|---|---|
| Frontend (`ProductCard`, `Cart`, `Checkout`) | Affichage de `[object Object] MAD`, `price * quantity` donne `NaN`, total du panier faux |
| Orders | Le calcul `total = price * quantity` lève une erreur ou donne `NaN` : la création de commande échoue |
| Tests et autres clients | Échec de validation de schéma |

Conséquences : commandes impossibles, totaux faux, ventes perdues. Le déploiement de Catalog a réussi (aucune erreur au démarrage), mais il a cassé d'autres services. La cause est que le contrat a été modifié sans prévenir les consommateurs. Cela montre le couplage de contrat : l'indépendance de déploiement n'est réelle que si les contrats sont stables.

## Q5. Comparaison des approches

| Approche | Principe | Avantages | Inconvénients |
|---|---|---|---|
| Modifier sur place | Changer `price` directement | Simple | Casse tous les consommateurs, déploiement coordonné obligatoire |
| Versionnement par URL | `/products` (v1) et `/v2/products` | Clair, v1 intacte, migration à son rythme | Deux versions à maintenir |
| Versionnement par header | `Accept: application/vnd.catalog.v2+json` | URL stable | Moins visible, plus difficile à tester |
| Changement additif | Garder `price` (nombre), ajouter `currency` | Rétrocompatible : les clients ignorent les champs inconnus | Le champ ancien reste le temps de la transition |

**Choix : changement additif en v1 + `/v2/products`** avec la nouvelle structure, puis dépréciation progressive de v1.
- Le frontend et Orders ne cassent pas : aucun champ n'est retiré et aucun type ne change.
- Les nouveaux consommateurs adoptent `/v2` quand ils le décident.
- Principe appliqué : une évolution doit être rétrocompatible (tolerant reader). Un changement incompatible passe par une nouvelle version.

## Q6. Stratégie d'évolution adoptée et implémentation

Règles d'équipe :
1. Aucun champ n'est supprimé ni changé de type dans une version existante.
2. Un nouveau champ peut être ajouté (les consommateurs doivent ignorer les champs inconnus).
3. Un changement incompatible exige une nouvelle version d'URL (`/v2/...`) et l'accord des consommateurs.
4. Une version ancienne est marquée dépréciée (headers `Deprecation: true` et `Link: <...>; rel="successor-version"`) avant d'être retirée.

Implémentation dans Catalog :
- `GET /products` et `GET /products/{id}` (v1) : `price` reste un nombre ; le champ `currency` est ajouté ; headers de dépréciation.
- `GET /v2/products` et `GET /v2/products/{id}` : `price = { "amount": number, "currency": "MAD" }`.

Démonstration (captures dans `docs/tests/`) :
- v1 renvoie `price: 8499` et `currency: "MAD"`.
- v2 renvoie `price: {"amount": 8499, "currency": "MAD"}`.
- Le frontend affiche toujours les produits (consommateur existant intact).
- Orders crée toujours des commandes avec le prix de v1.

Plan de migration : Orders et le frontend passent à `/v2/products` quand ils sont prêts, puis v1 est retirée.