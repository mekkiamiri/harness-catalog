<div align="center">

# pc-advisor

**Acheter le bon ordinateur pour développer et faire tourner de l'IA en local, avec de vrais prix.**

Tu décris ton besoin. pc-advisor lit les boutiques au moment de la recherche (neuf et reconditionné, France et UE),
écarte les offres qui ne peuvent pas y répondre et classe les autres, pièges déjà vérifiés :
RAM soudée, processeur trop faible, délai de retour court, clavier QWERTZ.

[Installer](#installer-en-deux-commandes) · [Déroulé](#déroulé-dune-session) · [Sources](docs/sources.md) · [Règles](#les-règles-dachat) · [English](README.md)

</div>

---

## Pourquoi

Demander à une IA « quel PC acheter ? » donne des prix tirés de sa mémoire : souvent vieux d'un an, parfois faux
du simple au double. Et les pièges qui coûtent cher sont dans les détails : un mini PC dont les 16 Go sont soudés et
ne passeront jamais à 32, un « PC portable IA » avec un processeur d'entrée de gamme, une boutique qui garde 15 %
si tu le renvoies.

pc-advisor corrige les deux :

- **De vrais prix** : chaque prix est lu sur la page de la boutique au moment de la recherche, avec son lien et sa date.
- **Les règles d'un acheteur averti, en code** : chaque piège rencontré lors d'un vrai achat est devenu une vérification.
- **Il part de ton besoin**, pas d'un produit déjà choisi.
- **Aucun lien affilié, aucun service payant.** Il tourne sur ta machine avec ton propre modèle.

## Installer en deux commandes

Il faut [Claude Code](https://code.claude.com) et [uv](https://docs.astral.sh/uv/getting-started/installation/).

```
/plugin marketplace add mekkiamiri/harness-catalog
/plugin install pc-advisor@harness-catalog
```

Ensuite, dis simplement *« je veux un PC pour du dev et de l'IA locale, autour de 800 € »* ou lance `/pc-advisor:need`.

## Déroulé d'une session

1. **`/pc-advisor:need`** : quelques questions, chacune avec une ligne qui explique à quoi elle sert (budget, RAM minimum, format, système, neuf ou reconditionné).
2. **`/pc-advisor:search`** : le serveur MCP lit les boutiques, vérifie chaque offre et classe celles qui conviennent. Tu obtiens un tableau avec liens, prix, dates et points de vigilance, puis une recommandation claire.
3. **`/pc-advisor:listing`** : colle une annonce Leboncoin, Back Market ou eBay ; tu obtiens les caractéristiques trouvées, les signaux d'alerte, les questions à poser au vendeur et les tests à faire sur place.

Exemple réel du 15 novembre 2026, besoin = mini PC, 32 Go minimum, 900 € maximum :

| # | Prix | Machine | Processeur (niveau) | RAM | Attention |
|---|---|---|---|---|---|
| 1 | 830 € | GMKtec K8 Plus | Ryzen 7 8845HS (5) | 32 Go, extensible | Retour 7 jours, 15 % de frais |
| 2 | 859 € | Minisforum UM790 Pro | Ryzen 9 7940HS (5) | 32 Go | |
| 4 | 570 € | GMKtec K16 | Ryzen 7 7735HS (4) | 32 Go | Retour 7 jours, 15 % de frais |

488 offres lues dans 7 boutiques, 426 écartées par les vérifications (RAM soudée sous 32 Go, rupture, hors budget, processeur faible…).

## Les règles d'achat

| Vérification | Pourquoi |
|---|---|
| **RAM soudée sous ton minimum = rejetée** | La mémoire LPDDR, les puces Apple, Ryzen AI Max et Intel Core Ultra 200V ne s'étendent jamais. |
| **Processeur faible rejeté pour le dev** | N100/N150, Celeron, Core 3 ou U300 sont vendus comme « PC de dev » ; ce sont des machines de bureautique. |
| **Pièges des processeurs expliqués** | Suffixes U, HS, T ; le « 7730U » est une puce Zen 3 de 2021 renommée. |
| **Barebones et machines à compléter à part** | Leur prix n'inclut ni la RAM, ni le SSD, ni le système. |
| **Alertes sur les conditions des boutiques** | Retour en 7 jours avec 15 % de frais, retour à tes frais, remboursement dégressif. |
| **Alerte QWERTZ** | Les reconditionneurs allemands vendent souvent des portables au clavier allemand. |
| **Reconditionné contre neuf** | En 2026, certains Mac reconditionnés coûtent plus cher que le modèle plus récent neuf. |
| **Honnêteté** | Un prix non lu par les outils n'est jamais présenté comme vérifié ; les sources absentes ou bloquées sont nommées. |

## Sources

Lues automatiquement : GMKtec, Beelink, Minisforum, Ninkear, Chuwi, ACEMAGIC (boutiques officielles UE) et l'Apple Store France (neuf et reconditionné certifié).
Prévues : Lapstore, Refurbed, Label Emmaüs, AfB. Jamais lues automatiquement (protégées contre les robots) : Leboncoin, Back Market, Amazon, eBay, ainsi que Costco France (pas de catalogue public à lire pour l'instant, carte de membre obligatoire). Pour celles-là, tu reçois des recherches toutes prêtes et l'analyse d'annonce.
Détails, méthodes et conditions de retour : [docs/sources.md](docs/sources.md).

pc-advisor lit poliment : identifiant honnête, robots.txt respecté, une requête par seconde et par site, cache de 6 heures, et **aucune tentative de contourner une protection**.

## Limites

- Les prix bougent : vérifie toujours la configuration exacte au panier.
- Les niveaux de processeur sont un repère d'achat, pas un banc de test.
- Une boutique qui change sa page peut casser son connecteur : la recherche le signale et continue avec les autres.

## Licence

MIT. Sans lien avec aucune boutique ni marque.
