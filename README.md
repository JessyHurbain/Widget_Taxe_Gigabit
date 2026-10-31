# TaxeGigabit

Un widget de bureau minimaliste, en Python pur (Tkinter + psutil), qui affiche en temps
réel le volume de données reçues par la machine et **ce que ce volume représenterait au
taux de la « taxe gigabit »** : 0,055 € par gigaoctet, telle que la prévoit l'amendement
n° I-1358 au projet de loi de finances pour 2027.

Le widget ne paie rien, ne facture personne et n'envoie aucune donnée : il lit les
compteurs d'octets de la carte réseau et applique une multiplication.

```
┌──────────────────────────────────────┐
│ ↓  1,67 Ko/s   ↑  1,01 Ko/s   ≡  ?  × │
│ Σ  9,251 Go  ·  taxe  0,509 €         │
└──────────────────────────────────────┘
```

- `↓` / `↑` : débit descendant et montant instantané, lissé.
- `Σ` : volume cumulé depuis la première utilisation (conservé entre les sessions).
- `taxe` : montant correspondant, au taux de 0,055 €/Go.
- `≡` : détail par jour. `?` : note « à propos ». `×` : quitter.
- Le widget et ses panneaux se déplacent à la souris et restent dans la zone utile de
  l'écran (au-dessus de la barre des tâches ou du Dock).

## À quoi ça sert

Un taux au gigaoctet ne dit rien. « 0,055 €/Go » est un nombre qu'on ne peut pas
évaluer sans le confronter à un usage réel. Le widget fait cette conversion en continu,
à l'échelle d'une machine :

| Contenu | Volume | Taxe |
|---|---|---|
| PDF de 5 Mo | 0,005 Go | 0,000275 € |
| Album musical | 0,1 Go | 0,0055 € |
| Épisode de série HD | 1,5 Go | 0,0825 € |
| Film en 4K | 15 Go | 0,825 € |
| Saison 4K complète | 120 Go | 6,60 € |
| GTA VI (taille annoncée sur PS5) | 210 Go | 11,55 € |
| 1 To | 1 000 Go | 55,00 € |

Et par profil d'usage, ramené au mois :

| Profil | Volume mensuel | Taxe mensuelle | Sur l'année |
|---|---|---|---|
| Navigation, mails, musique | ~15 Go | 0,83 € | 9,90 € |
| Streaming 4 h/jour HD | ~180 Go | 9,90 € | 118,80 € |
| Streaming 4 h/jour 4K | ~840 Go | 46,20 € | 554,40 € |
| Foyer « tous usages » | 300 Go | 16,50 € | 198 € |

**Point essentiel : ces montants ne sont pas une facture pour l'utilisateur.** Le
dispositif met la taxe à la charge de l'émetteur — le fournisseur de contenu —, pas de
l'abonné. Ce que ces chiffres mesurent, c'est l'assiette qu'un foyer représente, et donc
ce qui, en pratique, tendrait à se répercuter dans le prix des services.

## Installation

Prérequis : Python 3.8+, Tkinter, psutil.

```bash
# Debian / Ubuntu / Linux Mint
sudo apt install python3-tk python3-psutil

# macOS (Python de python.org, Tk inclus)
pip3 install psutil

# Windows (Python de python.org, Tk inclus)
pip install psutil
```

Tkinter est fourni avec les installeurs officiels Windows et macOS ; sous Linux il est
presque toujours présent, sinon le paquet `python3-tk` le fournit. Si Tkinter manque, le
programme s'arrête avec un message indiquant la commande adaptée au système.

## Lancement

```bash
python3 taxe_gigabit.py     # Linux, macOS
python taxe_gigabit.py      # Windows
```

`Ctrl+C` dans le terminal sauvegarde l'état puis quitte proprement. Le bouton `×` fait
la même chose.

## Ce que la loi prévoit

Texte de référence : **amendement n° I-1358** (PLF 2027, adopté en commission),
articles 302 bis ZP à 302 bis ZS du code général des impôts, chapitre XXI
« Taxe sur les producteurs de données numériques ».

| Disposition | Contenu |
|---|---|
| Assiette (art. 302 bis ZP) | Les flux de données numériques **émises** par les fournisseurs de contenu vers les clients — donc le trafic descendant chez l'abonné, pas son upload |
| Taux (art. 302 bis ZR) | Somme des volumes relevés, en gigaoctets, × **0,055 €** |
| Seuil | **Aucun** : la taxe porte dès le premier gigaoctet |
| Plafond (art. 302 bis ZR) | 15 % du chiffre d'affaires réalisé en France, ou 2 % du chiffre d'affaires total de l'émetteur |
| Collecte (art. 302 bis ZQ) | Mesure consolidée et anonymisée par les fournisseurs d'accès, sous supervision de l'ARCEP et de la DGFiP, transmission **trimestrielle**, sans inspection du contenu ni de la destination |
| CDN (art. 302 bis ZQ) | Si un réseau de diffusion met le contenu en cache, le volume retenu est la **somme des flux sortant** du réseau |
| Paiement (art. 302 bis ZS) | Groupes établis en France : mêmes modalités que l'impôt sur les sociétés. Groupes sans entité française : paiement en euros avant le 30 mars de l'année suivante, sur avis d'imposition émis avant le 30 janvier |
| Rendement annoncé | 10 Md€, pour un trafic estimé par l'ARCEP à 200 milliards de Go par an |

## Ce qui est réellement en jeu

### 1. Le problème visé est réel

L'exposé sommaire de l'amendement pose un constat difficile à contester : les acteurs
numériques étrangers vendent aux mêmes clients, utilisent les mêmes infrastructures et
bénéficient des mêmes services publics, mais leur assiette fiscale est un bénéfice
auto-déclaré, dont la localisation est un choix comptable. La taxe cherche une assiette
« non délocalisable » : des octets qui arrivent physiquement chez des abonnés français.
C'est l'idée la plus solide du texte.

### 2. Mais l'octet n'est pas une mesure de valeur

Deux services identiques peuvent différer d'un facteur dix en volume selon leur encodage.
Taxer le volume, c'est taxer une caractéristique technique, pas la rente économique
visée. Une plateforme très rentable et peu bavarde en données (logiciel B2B, publicité
ciblée) échappe largement à l'impôt, tandis qu'un service gratuit, public ou associatif à
gros trafic — université, miroir de logiciels libres, média de service public — serait
taxé comme un hyperscaler, faute de seuil.

### 3. Le texte promet deux choses incompatibles

L'exposé sommaire attend 10 Md€ sur 200 milliards de Go **et** espère que les émetteurs
« recourent aux technologies les plus avancées en matière de compression ». Ces deux
objectifs s'annulent : si la compression fonctionne, l'assiette baisse et le rendement
avec elle. On ne peut pas présenter la diminution de la base comme une vertu écologique
et comme une recette budgétaire.

### 4. Le plafond change la nature de l'impôt selon le secteur

À 15 % du CA France ou 2 % du CA total, un acteur vidéo à très fort volume s'arrête au
plafond, tandis qu'un éditeur à faible volume et forte marge paie le tarif plein. La
charge effective dépend alors du rapport entre volume de données et chiffre d'affaires,
c'est-à-dire du modèle économique — un critère que le législateur n'a pas voulu retenir.

### 5. La mesure est conventionnelle

L'article 302 bis ZQ renvoie la méthode à un décret et tranche le cas des CDN par une
convention : « la somme des flux sortant ». Déplacer un cache, changer de prestataire de
diffusion, activer un chiffrement de bout en bout ou s'appuyer sur du stockage local
modifie l'assiette sans qu'aucune activité économique n'ait changé. Une base fiscale qui
dépend de l'architecture réseau est une base contestable — et contestée.

### 6. L'incidence retombe sur l'utilisateur

Une taxe sur un flux intermédiaire n'est pas absorbée par celui qui la déclare : elle se
répercute dans les prix (abonnements, services financés par la publicité) ou se déplace
dans les choix d'infrastructure, loin des sièges des plateformes. L'objectif affiché —
faire contribuer les acteurs mondialisés — peut se transformer en hausse du coût d'accès
pour les ménages français.

### 7. Le vrai sujet reste intact

Le volume de données ne dit rien de l'endroit où le bénéfice est déclaré, or c'est
exactement le décalage que l'exposé sommaire décrit. Un impôt sur les octets ne répare
pas un problème de territorialité. La logique d'un impôt sur le chiffre d'affaires
(art. 299 CGI, « taxe sur les services numériques ») a ses propres limites, mais elle
vise au moins une valeur monétaire.

### 8. Le volet vie privée est plutôt bien traité

À décharge du texte : la mesure porte sur des compteurs d'octets par opérateur, sans
inspection des paquets, sans contenu et sans destination, sous supervision de l'ARCEP et
de la DGFiP. Ce widget fait exactement la même chose à l'échelle d'une machine : il lit
`psutil.net_io_counters()`, c'est-à-dire des totaux d'octets fournis par le système, et
n'ouvre aucun paquet.

## Vie privée et données

- **Aucune connexion réseau** n'est effectuée par le widget, hors celles de tes autres
  applications.
- Seuls des **compteurs d'octets** sont lus. Aucun contenu, aucune adresse, aucun
  historique de navigation.
- L'état est un simple fichier JSON local, une entrée par jour :

  | Système | Emplacement |
  |---|---|
  | Linux | `$XDG_STATE_HOME/taxe_gigabit/etat.json` (défaut : `~/.local/state/taxe_gigabit/`) |
  | macOS | `~/Library/Application Support/TaxeGigabit/etat.json` |
  | Windows | `%LOCALAPPDATA%\TaxeGigabit\etat.json` |

  Contenu : `{"version": 1, "jours": {"2026-10-31": 9251123}}`, en octets. Supprimer le
  fichier remet le compteur à zéro.

## Configuration

Tout est regroupé en tête de `taxe_gigabit.py`.

| Constante | Rôle | Valeur par défaut |
|---|---|---|
| `TAUX_EUROS_PAR_GO` | Taux appliqué | `0.055` (taux de l'amendement) |
| `SEUIL_EXONERATION_GO` | Volume exonéré | `0.0` (le texte n'en prévoit aucun) |
| `COMPTER_UPLOAD` | Inclure l'upload dans l'assiette | `False` (l'assiette légale est descendante) |
| `OCTETS_PAR_GO` | Convention d'unité | `10 ** 9` (Go décimal ; `1024 ** 3` pour le Gio) |
| `INTERFACE` | Carte surveillée | `None` = toutes, ou `"wlan0"`, `"enp3s0"`… |
| `INTERVALLE_MS` | Rafraîchissement | `1000` |
| `MARGE_BAS` | Marge au-dessus du bas de la zone utile | `8` px |
| `ALPHA` | Opacité de la fenêtre | `0.88` |
| `JOURS_AFFICHES` | Lignes du panneau par jour | `14` |
| `SAUVEGARDE_S` | Fréquence d'écriture de l'état | `15` s |

Le texte du panneau `?` est dans la constante `APROPOS` ; les exemples chiffrés dans
`EXEMPLES`, et ils sont recalculés au taux courant.

## Build et release

Le widget se lance directement en Python, mais des binaires autonomes sont produits
pour les trois systèmes.

| Système | Commande | Artefact |
|---|---|---|
| Linux | `./build.sh` | `dist/TaxeGigabit-linux-<arch>.tar.gz` |
| macOS | `./build.sh` | `dist/TaxeGigabit-macos-<arch>.zip` (contient `TaxeGigabit.app`) |
| Windows | `build.bat` | `dist\TaxeGigabit.exe` |

Chaque script crée un environnement `.build-venv`, y installe PyInstaller et psutil,
puis compile en un seul fichier (`--onefile --windowed`). PyInstaller ne fait pas de
compilation croisée : un binaire Windows se produit sous Windows, un binaire macOS
sous macOS.

Les trois artefacts sont aussi construits automatiquement par la CI
(`.github/workflows/release.yml`) : pousser un tag de version compile les trois
systèmes et publie une release GitHub avec les fichiers.

```bash
git tag v1.0.0
git push origin v1.0.0
```

Les binaires ne sont pas signés : Windows SmartScreen et Gatekeeper afficheront un
avertissement. Sous macOS, ouvrir par clic droit → « Ouvrir », ou lever la quarantaine :
`xattr -d com.apple.quarantine TaxeGigabit.app`.

## Limites connues

- **Ce n'est pas le calcul de la taxe réelle.** L'assiette légale est mesurée par les
  fournisseurs d'accès, par émetteur ; une carte réseau locale ne sait ni qui émet les
  données ni combien de clients sont derrière la même box.
- **Le plafonnement n'est pas modélisé** : il dépend du chiffre d'affaires de chaque
  émetteur. Les montants affichés sont ceux d'avant plafond.
- **Unité ambiguë** : le texte dit « gigaoctet » sans trancher entre 10⁹ et 1024³ octets,
  soit environ 7 % d'écart. Le Go décimal est retenu, la constante est modifiable.
- **Compteurs agrégés** : le trafic de bouclage (`lo`) est inclus quand `INTERFACE` vaut
  `None` ; l'exclure suppose de nommer la carte.
- **Pas d'attribution par émetteur**, par construction.
- Le panneau `?` mesure environ 960 px de haut : au-delà de ~970 px il basculerait en
  haut de l'écran et mordrait sur le widget.

## Portabilité

- Police à chasse fixe choisie parmi celles réellement installées (DejaVu Sans Mono,
  Liberation Mono, Ubuntu Mono, Menlo, Monaco, Consolas, Courier New, Courier).
- Boutons dessinés en `Label` : les `tk.Button` natifs ignorent les couleurs sous macOS
  et cassent le style sombre.
- Zone utile détectée par `SPI_GETWORKAREA` (Windows) ou `_NET_WORKAREA` (X11), avec une
  marge de secours si la détection échoue ; écran plein sous macOS.
- Conscience du DPI activée sous Windows.
- Développé et vérifié sous Linux Mint / X11. Les chemins Windows et macOS sont
  implémentés mais n'ont pas été validés sur ces systèmes.

## Sources

- Amendement n° I-1358 (PLF 2027), art. 302 bis ZP à ZS — texte fourni, cité ci-dessus.
- Taille annoncée de GTA VI (210 Go sur PS5, non confirmée par l'éditeur) :
  [jeuxvideo.com](https://www.jeuxvideo.com/news/2111124/gta-6-l-espace-necessaire-pour-l-installer-fait-peur-aux-joueurs-surtout-par-rapport-a-gta-5.htm),
  [overclock3d.net](https://overclock3d.net/news/software/grand-theft-auto-vi-has-a-200-gb-download-size-on-ps5/),
  [dlcompare.com](https://www.dlcompare.com/gaming-news/gta-6-preload-date-download-size-and-how-to-preload-on-ps5-and-xbox-86486).
- Estimation ARCEP de 200 milliards de Go/an et rendement de 10 Md€ : exposé sommaire de
  l'amendement.
