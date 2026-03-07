# Transparence Nationale

Les élus français sont tenus par la loi de déclarer leur patrimoine et leurs revenus à la HATVP (Haute Autorité pour la Transparence de la Vie Publique). Ces déclarations sont publiques. Ce site les rend lisibles.

---

## Ce que contient le site

Pour chaque élu : patrimoine total, immobilier, placements financiers, revenus annuels, participations dans des sociétés, instruments financiers détenus, et l'historique de ses mandats.

Les données sont présentées brutes, sans commentaire éditorial. Rien n'est ajouté, rien n'est interprété.

---

## Comment ça a été construit

1. **Collecte** — Les déclarations sont récupérées automatiquement depuis les APIs et flux XML de la HATVP, ainsi que depuis data.gouv.fr et l'Assemblée nationale.
2. **Extraction** — Pour les déclarations au format PDF (souvent scannés), un parseur avec OCR extrait les chiffres clés.
3. **Structuration** — Les données sont normalisées dans un fichier JSON unique, une entrée par ��lu.
4. **Affichage** — Une interface web statique, rapide, sans base de données, affiche ces données avec des filtres et des tris.

Le tout est open source. Les scripts de collecte sont dans `/scripts`, le code de l'interface dans `/src`.

---

## Sources

- [HATVP](https://www.hatvp.fr) — déclarations de patrimoine et d'intérêts (XML et PDF publics)
- [Assemblée nationale](https://www.assemblee-nationale.fr) — données sur les mandats et les fonctions
- [data.gouv.fr](https://www.data.gouv.fr) — open data gouvernemental

---

## Cadre légal

Ce projet ne publie aucune donnée nouvelle. Toutes les informations affichées sont déjà accessibles au public, sur les sites officiels listés ci-dessus.

La loi du 11 octobre 2013 relative à la transparence de la vie publique (dite « loi Sapin 1 ») impose aux élus de déposer ces déclarations et en rend la consultation possible à toute personne. La HATVP publie elle-même ces données en open data.

Ce site est un agrégateur, pas un éditeur. Il ne formule aucun jugement, ne hiérarchise pas les individus par ordre de « suspicion », et ne croise pas les données avec des sources tierces.

---

## Limites et mises en garde

Ce projet a des limites réelles. Il est important de les connaître avant d'utiliser ces données.

- **Décalage temporel.** Les déclarations sont déposées à l'entrée et à la sortie d'un mandat. Entre les deux, la situation patrimoniale d'un élu peut avoir évolué significativement.
- **Erreurs d'extraction.** Le parsing de PDFs scannés via OCR est imparfait. Des chiffres peuvent être mal lus, tronqués ou absents. Toujours vérifier sur la source officielle avant de publier.
- **Couverture incomplète.** Tous les élus ne sont pas couverts avec le même niveau de détail. Certaines déclarations sont partielles ou inexploitables techniquement.
- **Données déclaratives.** Ce site retranscrit ce que les élus ont eux-mêmes déclaré. Il ne vérifie pas l'exactitude de ces déclarations — c'est le rôle de la HATVP.
- **Mises à jour manuelles.** La base de données n'est pas mise à jour en temps réel. Elle peut ne pas refléter les déclarations les plus récentes.

En cas de doute sur une donnée, la source de référence est toujours [hatvp.fr](https://www.hatvp.fr).

---

## Licence

MIT — open source, à but non lucratif.

Les contributions sont bienvenues : [issues](https://github.com/oiIOIioiI0IioiIOIio/transparence-nationale/issues) et pull requests ouverts.