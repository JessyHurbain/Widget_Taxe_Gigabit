#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaxeGigabit — mini widget de bureau « taxe gigabit ».
Tkinter + psutil, 100 % Python, sans cadre ni barre de titre.

Barème conforme à l'amendement n° I-1358 (PLF 2027), art. 302 bis ZP à ZS,
« taxe sur les producteurs de données numériques » :

    taxe = volume de données produit, en gigaoctets, × 0,055 €

- l'assiette est le volume ÉMIS vers l'abonné, donc le trafic descendant :
  l'upload de l'utilisateur n'entre pas dans l'assiette ;
- le dispositif ne prévoit aucun seuil d'exonération ;
- la taxe est due par l'émetteur (fournisseur de contenu), pas par l'abonné :
  le widget affiche une estimation de ce que représenterait le trafic de
  cette machine, à titre indicatif ;
- le plafonnement légal (15 % du CA France ou 2 % du CA total de l'émetteur)
  n'est pas calculable à partir du seul volume : le montant affiché est
  celui d'avant plafond.

Mémoire : les volumes sont cumulés par jour dans un fichier d'état JSON et
rechargés au lancement, donc la taxe ne repart plus de zéro à chaque session.
Boutons : ≡ ouvre le détail par jour, ? ouvre la note « à propos ».
Le widget et ses deux panneaux se déplacent à la souris, sans sortir de l'écran.

PORTABILITÉ (Linux, macOS, Windows)
- police à chasse fixe choisie parmi celles réellement installées sur la machine ;
- boutons plats dessinés en Label : les tk.Button natifs ignorent les couleurs
  sous macOS et cassent le style sombre, alors qu'un Label est identique partout ;
- zone utile du bureau détectée (workarea Windows, _NET_WORKAREA sous X11) pour
  ne pas se poser sous la barre des tâches ni sous le Dock ;
- fichier d'état rangé selon la convention du système (XDG sous Linux,
  Application Support sous macOS, LOCALAPPDATA sous Windows) ;
- conscience du DPI activée sous Windows, sinon le texte est flou.

Lancement :  python3 taxe_gigabit.py
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import date

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox
except ImportError:                     # Tk absent : message utile par système
    sys.exit(
        "Tkinter est requis.\n"
        "  Linux (Mint/Debian) : sudo apt install python3-tk\n"
        "  Windows / macOS     : réinstaller Python depuis python.org\n"
        "                        en laissant l'option Tcl/Tk cochée."
    )

try:
    import psutil
except ImportError:
    sys.exit(
        "psutil est requis.\n"
        "  pip install psutil\n"
        "  (Debian/Mint : sudo apt install python3-psutil)"
    )

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Barème de la taxe (amendement n° I-1358, art. 302 bis ZR) ---------------
TAUX_EUROS_PAR_GO = 0.055     # taux légal : 0,055 € par gigaoctet produit
SEUIL_EXONERATION_GO = 0.0    # le dispositif n'en prévoit aucun
COMPTER_UPLOAD = False        # False = assiette légale (flux descendants seuls)

# Unité de volume : le texte parle de « gigaoctet » sans trancher entre les deux
# conventions. 10**9 = Go décimal (usage SI / ARCEP, retenu ici) ; utiliser
# 1024 ** 3 pour la convention binaire (Gio).
OCTETS_PAR_GO = 10 ** 9

# --- Source des statistiques -------------------------------------------------
INTERFACE = None              # None = toutes interfaces agrégées,
                              # ou "wlan0", "enp3s0", "eth0"... (voir `ip -br link`)

# --- Mémoire des taxes -------------------------------------------------------
SAUVEGARDE_S = 15             # intervalle d'écriture sur disque (secondes)
JOURS_AFFICHES = 14           # nombre de lignes du panneau « taxe par jour »

# --- Comportement / placement ------------------------------------------------
INTERVALLE_MS = 1000          # rafraîchissement (ms)
MARGE_BAS = 8                 # px au-dessus du bas de la zone utile
MARGE_BAS_SECOURS = {"win32": 48, "darwin": 96}.get(sys.platform, 48)
                              # utilisé seulement si la zone utile n'a pas pu
                              # être détectée : barre des tâches ou Dock masqué
ALPHA = 0.88                  # opacité de la fenêtre (0.0 → 1.0)
LISSAGE = 0.45                # 0 = très mou, 1 = brut (débit instantané)

# --- Style « terminal » ------------------------------------------------------
COULEUR_FOND = "#101010"
COULEUR_SURVOL = "#1f1f1f"
COULEUR_BORDURE = "#2b2b2b"
COULEUR_TEXTE = "#00e08a"
COULEUR_SOURDINE = "#7f8c8d"
COULEUR_ALERTE = "#ff5f56"

FAMILLES_MONO = ("DejaVu Sans Mono", "Liberation Mono", "Ubuntu Mono",
                 "Menlo", "Monaco", "Consolas", "Courier New", "Courier")

# Remplacées au démarrage par une famille réellement installée
POLICE = ("Courier", 10, "bold")
POLICE_SOURDINE = ("Courier", 9)
POLICE_BOUTON = ("Courier", 10, "bold")

LARGEUR_APROPOS = 520         # px : largeur de repli du texte « à propos »
PART_ECRAN_PANNEAU = 0.8      # le panneau « à propos » ne dépasse pas cette part
                              # de la hauteur d'écran ; au-delà, il défile

UNITES = ("o/s ", "Ko/s", "Mo/s", "Go/s")

# =============================================================================
# TEXTE DU PANNEAU « À PROPOS »
# =============================================================================

APROPOS = (
    ("Ce que fait ce widget",
     "TaxeGigabit mesure le trafic descendant de cette machine et lui applique le barème "
     "de l'amendement n° I-1358 (PLF 2027, art. 302 bis ZP à ZS) : 0,055 € par gigaoctet, "
     "sans seuil d'exonération. Il ne paie rien et ne facture personne : la taxe serait "
     "due par l'émetteur des données, pas par l'abonné. Le widget rend visible l'ordre de "
     "grandeur que représenterait un foyer."),
    ("Pourquoi il existe",
     "Un taux au gigaoctet est abstrait : 0,055 € ne dit rien tant qu'il n'est pas "
     "confronté à un usage réel. Le widget transforme un article de loi en chiffre "
     "quotidien et permet de juger le dispositif sur pièces : 100 Go de vidéo pèsent "
     "5,50 €, un foyer à 300 Go par mois en représenterait 16,50 €."),
    ("Pourquoi la loi est en tension avec l'économie numérique",
     "· L'assiette n'est pas la valeur. Deux services identiques peuvent différer d'un "
     "facteur dix en volume selon leur encodage : on taxe une caractéristique technique, "
     "pas la rente visée.\n\n"
     "· Le texte se contredit : il attend 10 Md€ pour 200 milliards de Go, tout en "
     "espérant que les émetteurs compressent davantage. Si l'assiette baisse, le rendement "
     "baisse d'autant.\n\n"
     "· Le plafond (15 % du CA France, 2 % du CA total) change l'impôt selon le secteur : "
     "un acteur vidéo plafonne, un éditeur à faible volume et forte marge paie plein "
     "tarif.\n\n"
     "· Aucun seuil n'est prévu : un service public, une université ou un miroir libre à "
     "gros trafic seraient traités comme un hyperscaler.\n\n"
     "· La mesure est conventionnelle : l'art. 302 bis ZQ renvoie la méthode à un décret "
     "et pose que, pour un CDN, le volume vaut « la somme des flux sortant ». Changer de "
     "CDN ou déplacer un cache modifie l'assiette sans changer l'activité.\n\n"
     "· L'incidence retombe sur l'utilisateur : la taxe se répercute dans les prix ou se "
     "déplace dans l'architecture réseau, loin des sièges des plateformes.\n\n"
     "· Le vrai sujet reste intact : le volume ne dit rien de l'endroit où le bénéfice "
     "est déclaré. Un impôt sur les octets ne répare pas un problème de territorialité ; "
     "la logique d'un impôt sur le CA (art. 299 CGI) a ses limites, mais vise au moins "
     "une valeur."),
    ("Ce que le widget ne fait pas",
     "Il ne calcule pas le plafonnement, qui dépend du CA de chaque émetteur ; il ne "
     "répartit pas par émetteur, alors que le texte exige d'identifier l'entreprise "
     "émettrice, ce qu'une carte réseau locale ne peut pas faire ; il ne prédit pas ce "
     "que la DGFiP collecterait réellement."),
)


# =============================================================================
# UTILITAIRES
# =============================================================================

def fmt_debit(octets_par_s: float) -> str:
    """Débit en largeur fixe (10 caractères) pour éviter que le widget gigote."""
    v = max(float(octets_par_s), 0.0)
    i = 0
    while v >= 1024.0 and i < len(UNITES) - 1:
        v /= 1024.0
        i += 1
    # Deux décimales suffisent presque toujours, mais 3 ou 4 chiffres avant la
    # virgule font déborder le champ : on retire alors des décimales, plutôt
    # que de laisser le widget changer de largeur à chaque pic de trafic.
    for decimales in (2, 1, 0):
        nombre = f"{v:5.{decimales}f}"
        if len(nombre) == 5:
            break
    return f"{nombre} {UNITES[i]}".replace(".", ",")


def fmt_go(go: float) -> str:
    return f"{go:6.3f} Go".replace(".", ",")


def fmt_euros(montant: float) -> str:
    """Précision adaptée : à 0,055 €/Go, un faible volume reste lisible."""
    if montant < 10:
        return f"{montant:6.3f} €".replace(".", ",")
    return f"{montant:6.2f} €".replace(".", ",")


def fmt_euros_fin(montant: float) -> str:
    """Montant en euros avec assez de chiffres pour rester lisible sur 5 Mo."""
    if montant <= 0:
        return "0 €"
    decimales = min(6, max(2, 2 - math.floor(math.log10(montant))))
    texte = f"{montant:.{decimales}f}"
    if decimales > 2:
        texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",") + " €"


def lire_compteurs():
    """(octets_recus, octets_envoyes) cumulés, ou None si indisponible."""
    try:
        if INTERFACE:
            c = psutil.net_io_counters(pernic=True).get(INTERFACE)
            if c is None:
                return None
        else:
            c = psutil.net_io_counters()
    except Exception:
        return None
    return c.bytes_recv, c.bytes_sent


def taxe_de(octets: int) -> float:
    """Taxe légale pour un volume d'assiette, en euros (avant plafonnement)."""
    go = octets / OCTETS_PAR_GO
    return max(0.0, go - SEUIL_EXONERATION_GO) * TAUX_EUROS_PAR_GO


# -- adaptations au système ---------------------------------------------------

def activer_dpi() -> None:
    """Windows : rend le texte net sur les écrans à forte densité."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)     # Windows 8.1+
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()      # Windows 7
        except Exception:
            pass


def choisir_police(racine: tk.Tk) -> str:
    """Première famille à chasse fixe réellement installée sur la machine."""
    try:
        disponibles = set(tkfont.families(racine))
    except tk.TclError:
        return "Courier"
    for famille in FAMILLES_MONO:
        if famille in disponibles:
            return famille
    return "Courier"


def zone_utile(racine: tk.Tk) -> tuple[int, int, int, int]:
    """(x, y, largeur, hauteur) du bureau utilisable, hors barre des tâches/Dock."""
    sw, sh = racine.winfo_screenwidth(), racine.winfo_screenheight()

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                return (rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top)
        except Exception:
            pass

    elif sys.platform.startswith("linux"):
        try:
            sortie = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                                    capture_output=True, text=True,
                                    timeout=1).stdout
            # _NET_WORKAREA(CARDINAL) = 0, 0, 3520, 1047, 0, 0, ...
            nombres = [int(n) for n in
                       sortie.split("=")[-1].replace(",", " ").split()]
            if len(nombres) >= 4 and nombres[2] > 0 and nombres[3] > 0:
                return nombres[0], nombres[1], nombres[2], nombres[3]
        except Exception:
            pass

    return 0, 0, sw, sh


def moniteurs(racine: tk.Tk) -> list[tuple[int, int, int, int]]:
    """Rectangles (x, y, largeur, hauteur) des moniteurs, si connus.

    Sous X11, la zone utile couvre tout le bureau : avec deux écrans de
    hauteurs différentes, elle ne dit pas sur lequel on dessine. xrandr le dit.
    Ailleurs (et sous Wayland), la liste est vide et l'appelant se rabat sur la
    zone utile.
    """
    if not sys.platform.startswith("linux"):
        return []
    try:
        sortie = subprocess.run(["xrandr", "--listmonitors"],
                                capture_output=True, text=True,
                                timeout=1, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rects = []
    # « 0: +*eDP-1 1920/344x1080/194+1600+0  eDP-1 »
    motif = re.compile(r"\s*\d+:\s+\S*\s*(\d+)/(\d+)x(\d+)/(\d+)\+(-?\d+)\+(-?\d+)")
    for ligne in sortie.splitlines():
        trouve = motif.match(ligne)
        if trouve:
            largeur, _, hauteur, _, x, y = (int(v) for v in trouve.groups())
            rects.append((x, y, largeur, hauteur))
    return rects


def zone_moniteur(racine: tk.Tk, x: int, y: int,
                  secours: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Rectangle du moniteur qui contient (x, y), sinon le secours fourni."""
    for rect in moniteurs(racine):
        mx, my, mw, mh = rect
        if mx <= x < mx + mw and my <= y < my + mh:
            return rect
    return secours


def dossier_etat() -> str:
    """Dossier de l'état, rangé selon la convention de chaque système."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "TaxeGigabit")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library",
                            "Application Support", "TaxeGigabit")
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "taxe_gigabit")


FICHIER_ETAT = os.path.join(dossier_etat(), "etat.json")


VERROU = None      # garde le verrou d'instance ouvert pendant toute la session


def verrouiller_instance() -> bool:
    """Vrai si cette instance est seule, faux si une autre tourne déjà.

    Verrou noyau plutôt qu'un fichier de PID : il disparaît avec le processus,
    donc un plantage ne condamne pas les lancements suivants. Deux instances
    tiendraient chacune leur cumul en mémoire et écraseraient tour à tour le
    fichier d'état, en perdant la moitié du trafic mesuré.
    """
    global VERROU
    dossier = dossier_etat()
    try:
        os.makedirs(dossier, exist_ok=True)
        fichier = open(os.path.join(dossier, "instance.lock"), "a+")
    except OSError:
        return True                     # dossier inscriptible ? on continue
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fichier.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fichier.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fichier.close()
        return False
    VERROU = fichier                    # libéré à la sortie du processus
    return True


def chemin_ressource(nom_relatif: str) -> str:
    """Chemin d'un fichier joint, y compris dans un binaire PyInstaller (onefile)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nom_relatif)


def appliquer_icone(racine: tk.Tk) -> None:
    """Icône de fenêtre et de barre des tâches, si le fichier est présent."""
    try:
        image = tk.PhotoImage(file=chemin_ressource("assets/logo.png"))
    except (tk.TclError, OSError):
        return                          # lancé sans le dossier assets : on continue
    racine.iconphoto(True, image)       # True : s'applique aussi aux Toplevel
    racine._icone = image               # garder une référence, sinon Tk l'oublie


def bouton_plat(parent: tk.Widget, texte: str, commande,
                couleur_survol: str = COULEUR_TEXTE) -> tk.Label:
    """Bouton plat en Label : même rendu sombre sur Linux, macOS et Windows."""
    lbl = tk.Label(parent, text=texte, bg=COULEUR_FOND, fg=COULEUR_SOURDINE,
                   font=POLICE_BOUTON, padx=5, pady=2, cursor="hand2")
    lbl._est_bouton = True                 # épargné par le curseur de déplacement
    lbl._commande = commande

    def clic(_evt):
        commande()
        return "break"                     # n'enchaîne pas sur le glissement

    lbl.bind("<Button-1>", clic)
    lbl.bind("<Enter>", lambda _e: lbl.configure(fg=couleur_survol,
                                                 bg=COULEUR_SURVOL))
    lbl.bind("<Leave>", lambda _e: lbl.configure(fg=COULEUR_SOURDINE,
                                                 bg=COULEUR_FOND))
    return lbl


def _curseur_fleur(widget: tk.Widget) -> None:
    """Curseur « déplaçable » sur tout le panneau, sauf sur les boutons."""
    try:
        widget.configure(cursor="fleur")
    except tk.TclError:
        pass
    for enfant in widget.winfo_children():
        if getattr(enfant, "_est_bouton", False):
            continue
        if isinstance(enfant, tk.Scrollbar):
            continue                   # la barre garde son curseur de défilement
        _curseur_fleur(enfant)


def rendre_deplacable(fenetre: tk.Toplevel, conteneur: tk.Widget,
                      zone: tuple[int, int, int, int]) -> None:
    """Rend une fenêtre sans bordure déplaçable, en la gardant dans la zone utile.

    Les gestionnaires sont conservés en attributs de la fenêtre : Tk ne les
    expose pas, et cela les rend appelables hors événement (tests).
    """
    etat = {"decalage": None}

    def debut(evt):
        # Les contrôles qui ont leur propre glisser ne déplacent pas la fenêtre :
        # sans cela, tirer la barre de défilement déplacerait le panneau.
        if isinstance(evt.widget, (tk.Scrollbar, tk.Scale, tk.Entry, tk.Text)):
            etat["decalage"] = None
            return
        etat["decalage"] = (evt.x_root - fenetre.winfo_x(),
                            evt.y_root - fenetre.winfo_y())

    def fin(_evt):
        # Oublier le glisser au relâchement : sinon, passer au-dessus de la barre
        # bouton encore enfoncé déplacerait la fenêtre.
        etat["decalage"] = None

    def mouvement(evt):
        if etat["decalage"] is None:
            return
        dx, dy = etat["decalage"]
        w, h = fenetre.winfo_width(), fenetre.winfo_height()
        if w <= 1 or h <= 1:                   # avant la 1re réalisation
            w, h = fenetre.winfo_reqwidth(), fenetre.winfo_reqheight()
        zx, zy, zw, zh = zone
        x = max(zx, min(evt.x_root - dx, zx + zw - w))
        y = max(zy, min(evt.y_root - dy, zy + zh - h))
        fenetre.geometry(f"+{x}+{y}")

    fenetre._drag_debut = debut
    fenetre._drag_fin = fin
    fenetre._drag_mouvement = mouvement
    fenetre.bind("<Button-1>", debut)
    fenetre.bind("<ButtonRelease-1>", fin)
    fenetre.bind("<B1-Motion>", mouvement)
    _curseur_fleur(conteneur)


def placer_au_dessus(fenetre: tk.Toplevel, widget: "TaxeGigabit") -> None:
    """Colle un panneau au-dessus du widget, sur le moniteur qui le porte.

    Se placer d'après la seule zone utile ne suffit pas : elle couvre tout le
    bureau, si bien qu'avec deux écrans de hauteurs différentes le panneau peut
    sortir du plus petit. On raisonne donc dans le rectangle du moniteur du
    widget, et jamais en dehors.
    """
    fenetre.update_idletasks()
    w, h = fenetre.winfo_reqwidth(), fenetre.winfo_reqheight()
    r = widget.racine
    rx, ry = r.winfo_x(), r.winfo_y()
    rw, rh = r.winfo_width(), r.winfo_height()
    mx, my, mw, mh = zone_moniteur(r, rx + rw // 2, ry + rh // 2, widget._zone)

    x = max(mx, min(rx, mx + mw - w))
    y = ry - h - 8                     # au-dessus du widget, si la place existe
    if y < my:
        dessous = ry + rh + 8
        # Sinon en dessous, sinon en haut du moniteur : jamais hors de l'écran.
        y = dessous if dessous + h <= my + mh else my
    y = max(my, min(y, my + mh - h))
    fenetre.geometry(f"{w}x{h}+{x}+{y}")


# -- mémoire sur disque -------------------------------------------------------

def charger_jours() -> dict[str, int]:
    """Historique {AAAA-MM-JJ: octets d'assiette}, dict vide si absent/corrompu.

    Le filtrage se fait entrée par entrée : une seule valeur aberrante ne doit
    pas faire perdre tout l'historique, seulement la ligne illisible.
    """
    try:
        with open(FICHIER_ETAT, encoding="utf-8") as flux:
            donnees = json.load(flux)
        bruts = donnees.get("jours", {})
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(bruts, dict):
        return {}
    jours: dict[str, int] = {}
    for jour, valeur in bruts.items():
        try:
            octets = int(valeur)
        except (TypeError, ValueError):
            continue
        if octets > 0:
            jours[str(jour)] = octets
    return jours


def enregistrer_jours(jours: dict[str, int], position=None) -> None:
    """Écriture atomique : un plantage ne laisse pas un fichier tronqué."""
    dossier = os.path.dirname(FICHIER_ETAT)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    donnees = {"version": 1, "jours": jours}
    if position is not None:
        donnees["position"] = [int(position[0]), int(position[1])]
    temporaire = FICHIER_ETAT + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as flux:
        json.dump(donnees, flux, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(temporaire, FICHIER_ETAT)       # atomique aussi sous Windows


def charger_position() -> tuple[int, int] | None:
    """Dernière position choisie à la souris, None si absente ou illisible."""
    try:
        with open(FICHIER_ETAT, encoding="utf-8") as flux:
            brut = json.load(flux).get("position")
        x, y = int(brut[0]), int(brut[1])
    except (OSError, ValueError, TypeError, IndexError, AttributeError, KeyError):
        return None
    return (x, y)


EXEMPLES = (
    ("PDF de 5 Mo", 0.005),
    ("album musical de 100 Mo", 0.1),
    ("épisode de série HD (1,5 Go)", 1.5),
    ("film en 4K (15 Go)", 15.0),
    ("saison 4K complète (120 Go)", 120.0),
    ("GTA VI, taille annoncée sur PS5 (210 Go)", 210.0),
)


def section_exemples():
    """Section « à propos » calculée avec le taux courant, donc jamais périmée."""
    lignes = [f"· {libelle} : {fmt_euros_fin(go * TAUX_EUROS_PAR_GO)}"
              for libelle, go in EXEMPLES]
    return ("Ce que ça coûte concrètement", "\n".join(lignes))


# =============================================================================
# PANNEAU « TAXE PAR JOUR »
# =============================================================================

class PanneauJours:
    """Fenêtre sans bordure listant les jours mesurés, volumes et taxes."""

    def __init__(self, widget: "TaxeGigabit"):
        self.widget = widget
        self.f = tk.Toplevel(widget.racine)
        self.f.overrideredirect(True)
        self.f.configure(bg=COULEUR_FOND)
        self.f.attributes("-topmost", True)
        try:
            self.f.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass

        cadre = tk.Frame(self.f, bg=COULEUR_FOND, highlightthickness=1,
                         highlightbackground=COULEUR_BORDURE, padx=8, pady=6)
        cadre.pack(fill="both", expand=True)

        entete = tk.Frame(cadre, bg=COULEUR_FOND)
        entete.pack(fill="x")
        tk.Label(entete, font=POLICE_SOURDINE, fg=COULEUR_TEXTE, bg=COULEUR_FOND,
                 anchor="w",
                 text=f"taxe par jour · {TAUX_EUROS_PAR_GO:.3f} €/Go".replace(".", ","),
                 ).pack(side="left")
        bouton_plat(entete, " × ", self.fermer, COULEUR_ALERTE).pack(side="right")

        grille = tk.Frame(cadre, bg=COULEUR_FOND)
        grille.pack(fill="x", pady=(6, 0))
        self.lignes = []
        for i in range(JOURS_AFFICHES):
            lbl_date = tk.Label(grille, text="", font=POLICE_SOURDINE,
                                fg=COULEUR_SOURDINE, bg=COULEUR_FOND, anchor="w")
            lbl_date.grid(row=i, column=0, sticky="w")
            lbl_go = tk.Label(grille, text="", font=POLICE_SOURDINE,
                              fg=COULEUR_SOURDINE, bg=COULEUR_FOND, anchor="e")
            lbl_go.grid(row=i, column=1, sticky="e", padx=(14, 0))
            lbl_eur = tk.Label(grille, text="", font=POLICE_SOURDINE,
                               fg=COULEUR_SOURDINE, bg=COULEUR_FOND, anchor="e")
            lbl_eur.grid(row=i, column=2, sticky="e", padx=(10, 0))
            self.lignes.append((lbl_date, lbl_go, lbl_eur))

        self.lbl_pied = tk.Label(cadre, text="", font=POLICE_SOURDINE,
                                 fg=COULEUR_TEXTE, bg=COULEUR_FOND, anchor="w")
        self.lbl_pied.pack(fill="x", pady=(6, 0))
        bouton_plat(cadre, " réinitialiser le cumul ", self._reinitialiser,
                    COULEUR_SOURDINE).pack(anchor="e", pady=(4, 0))

        self.rafraichir()
        placer_au_dessus(self.f, widget)
        rendre_deplacable(self.f, cadre, widget._zone)

    # -- contenu --------------------------------------------------------------
    def rafraichir(self):
        jours = sorted(self.widget.jours.items(), reverse=True)
        aujourdhui = date.today().isoformat()

        for i, (lbl_date, lbl_go, lbl_eur) in enumerate(self.lignes):
            if i < len(jours):
                jour, octets = jours[i]
                couleur = COULEUR_TEXTE if jour == aujourdhui else COULEUR_SOURDINE
                lbl_date.config(text=f"{jour[8:10]}/{jour[5:7]}/{jour[2:4]}",
                                fg=couleur)
                lbl_go.config(text=fmt_go(octets / OCTETS_PAR_GO), fg=couleur)
                lbl_eur.config(text=fmt_euros(taxe_de(octets)), fg=couleur)
            else:
                for lbl in (lbl_date, lbl_go, lbl_eur):
                    lbl.config(text="")

        total_octets = sum(self.widget.jours.values())
        self.lbl_pied.config(
            text=f"cumul {fmt_go(total_octets / OCTETS_PAR_GO)}"
                 f"  ·  {fmt_euros(taxe_de(total_octets))}"
                 f"  ({len(jours)} j)"
        )

    def fermer(self):
        self.widget._panneau_ferme()

    def _reinitialiser(self):
        """Efface l'historique après confirmation : action irréversible."""
        if not messagebox.askyesno(
            "Réinitialiser le cumul",
            "Effacer tous les jours mesurés ? Cette action est irréversible.",
            parent=self.f,
        ):
            return
        self.widget.jours.clear()
        self.widget._sauvegarder()
        self.rafraichir()


# =============================================================================
# PANNEAU « À PROPOS »
# =============================================================================

class PanneauAPropos:
    """Note statique : ce que fait le widget, et les limites du dispositif."""

    def __init__(self, widget: "TaxeGigabit"):
        self.widget = widget
        self._defilable = False
        self.f = tk.Toplevel(widget.racine)
        self.f.overrideredirect(True)
        self.f.configure(bg=COULEUR_FOND)
        self.f.attributes("-topmost", True)
        try:
            self.f.attributes("-alpha", ALPHA)
        except tk.TclError:
            pass

        cadre = tk.Frame(self.f, bg=COULEUR_FOND, highlightthickness=1,
                         highlightbackground=COULEUR_BORDURE, padx=10, pady=8)
        cadre.pack(fill="both", expand=True)

        self.entete = tk.Frame(cadre, bg=COULEUR_FOND)
        self.entete.pack(fill="x")
        self.lbl_titre = tk.Label(self.entete, text="à propos · pourquoi ce widget",
                                  font=POLICE_SOURDINE, fg=COULEUR_TEXTE,
                                  bg=COULEUR_FOND, anchor="w")
        self.lbl_titre.pack(side="left")
        bouton_plat(self.entete, " × ", self.fermer, COULEUR_ALERTE).pack(side="right")

        # Le texte dépasse la hauteur d'un petit écran : il défile dans un
        # canevas, dont la hauteur est bornée à la zone utile. La barre
        # n'apparaît que si le contenu ne tient pas.
        corps = tk.Frame(cadre, bg=COULEUR_FOND)
        corps.pack(fill="both", expand=True, pady=(4, 0))

        self.zone = tk.Canvas(corps, bg=COULEUR_FOND, highlightthickness=0, bd=0,
                              width=LARGEUR_APROPOS)
        self.barre = tk.Scrollbar(corps, orient="vertical", width=9, bd=0,
                                  command=self.zone.yview,
                                  bg=COULEUR_BORDURE, troughcolor=COULEUR_FOND,
                                  activebackground=COULEUR_TEXTE,
                                  highlightthickness=0, elementborderwidth=0)
        self.zone.configure(yscrollcommand=self.barre.set)
        self.zone.pack(side="left", fill="both", expand=True)

        self.contenu = tk.Frame(self.zone, bg=COULEUR_FOND)
        self._fenetre = self.zone.create_window((0, 0), window=self.contenu,
                                                anchor="nw")
        self.contenu.bind("<Configure>", self._contenu_change)
        self.zone.bind("<Configure>", self._elargir_contenu)

        self.sections = []
        for titre, texte in APROPOS + (section_exemples(),):
            tk.Label(self.contenu, text=titre, font=POLICE_SOURDINE,
                     fg=COULEUR_TEXTE, bg=COULEUR_FOND, anchor="w",
                     justify="left").pack(fill="x", pady=(9, 2))
            corps_texte = tk.Label(self.contenu, text=texte, font=POLICE_SOURDINE,
                                   fg=COULEUR_SOURDINE, bg=COULEUR_FOND,
                                   anchor="w", justify="left",
                                   wraplength=LARGEUR_APROPOS)
            corps_texte.pack(fill="x")
            self.sections.append(corps_texte)

        self.pied = tk.Label(cadre,
                             text="amendement n° I-1358 · PLF 2027 · 0,055 €/Go",
                             font=POLICE_SOURDINE, fg=COULEUR_BORDURE,
                             bg=COULEUR_FOND, anchor="w")
        self.pied.pack(fill="x", pady=(8, 0))

        # Molette : Button-4/5 sous X11, delta sous Windows et macOS.
        self.f.bind("<Button-4>", lambda _e: self._molette(-1))
        self.f.bind("<Button-5>", lambda _e: self._molette(1))
        self.f.bind("<MouseWheel>",
                    lambda e: self._molette(-1 if e.delta > 0 else 1))

        self.f.update_idletasks()
        self._hauteur_adaptee()
        placer_au_dessus(self.f, widget)
        rendre_deplacable(self.f, cadre, widget._zone)

    # -- défilement -----------------------------------------------------------
    def _contenu_change(self, _evt=None):
        self.zone.configure(scrollregion=self.zone.bbox("all"))

    def _elargir_contenu(self, evt):
        self.zone.itemconfigure(self._fenetre, width=evt.width)

    def _hauteur_adaptee(self):
        """Borne la hauteur du canevas, barre comprise.

        Deux limites, et la plus contraignante l'emporte : la zone utile
        mesurée au lancement, et une part de la hauteur d'écran. La seconde
        rattrape les cas où la première ne décrit plus l'écran réel : moniteur
        plus petit, résolution changée, ou seconde sortie branchée après coup.
        """
        self.f.update_idletasks()
        _zx, _zy, _zw, zh = self.widget._zone
        # marges externes, bordure, remplissage, écarts, en-tête et pied
        marges = (2 * MARGE_BAS + 2 + 16 + 4 + 8
                  + self.entete.winfo_reqheight()
                  + self.pied.winfo_reqheight())
        r = self.widget.racine
        _mx, _my, _mw, mh = zone_moniteur(
            r, r.winfo_x() + r.winfo_width() // 2,
            r.winfo_y() + r.winfo_height() // 2, self.widget._zone)
        plafond = min(zh, mh - 2 * MARGE_BAS,
                      int(self.f.winfo_screenheight() * PART_ECRAN_PANNEAU))
        hauteur_max = max(180, plafond - marges)
        contenu = self.contenu.winfo_reqheight()
        self._defilable = contenu > hauteur_max
        self.zone.configure(height=min(contenu, hauteur_max))
        if self._defilable:
            self.barre.pack(side="right", fill="y", before=self.zone)
        else:
            self.barre.pack_forget()
            self.zone.yview_moveto(0)

    def _molette(self, pas):
        """Défile d'une unité ; laisse passer l'événement si rien ne déborde."""
        if not self._defilable:
            return None
        self.zone.yview_scroll(pas, "units")
        return "break"

    def fermer(self):
        self.widget._fermer_apropos()


# =============================================================================
# WIDGET
# =============================================================================

class TaxeGigabit:
    def __init__(self, racine: tk.Tk):
        self.racine = racine

        # Police réellement disponible sur cette machine
        global POLICE, POLICE_SOURDINE, POLICE_BOUTON
        famille = choisir_police(racine)
        POLICE = (famille, 10, "bold")
        POLICE_SOURDINE = (famille, 9)
        POLICE_BOUTON = (famille, 10, "bold")

        self._zone = zone_utile(racine)     # bureau utilisable (hors panneau/Dock)

        # Assiette cumulée par jour, rechargée depuis le disque
        self.jours = charger_jours()
        self.jour = date.today().isoformat()
        self._derniere_sauvegarde = time.monotonic()
        self.panneau = None
        self.a_propos = None

        # Débits instantanés (lissés)
        self.debit_down = 0.0
        self.debit_up = 0.0

        # None = compteurs illisibles au démarrage : le premier échantillon
        # exploitable servira de référence. Sans cette précaution, le tick
        # suivant compterait d'un coup tout le trafic depuis le démarrage de
        # la machine, et l'erreur serait ensuite écrite dans l'état.
        compteurs = lire_compteurs()
        self.prev_recv, self.prev_sent = (compteurs if compteurs
                                          else (None, None))
        self.prev_t = time.monotonic()
        self._taille = None
        self._pos_manuelle = charger_position()   # None = ancrage auto
        self._drag = None           # décalage curseur/fenêtre pendant un glissement

        self._construire()
        self._rafraichir()
        self._ancrer_si_besoin()
        self.racine.after(INTERVALLE_MS, self._tick)

    # -- interface ------------------------------------------------------------
    def _construire(self):
        r = self.racine
        r.overrideredirect(True)          # pas de bordure, pas de barre de titre
        r.configure(bg=COULEUR_FOND)
        r.attributes("-topmost", True)    # toujours au premier plan
        try:
            r.attributes("-alpha", ALPHA)  # compositeur requis (Cinnamon, DWM, Aqua)
        except tk.TclError:
            pass

        cadre = tk.Frame(r, bg=COULEUR_FOND, highlightthickness=1,
                         highlightbackground=COULEUR_BORDURE, padx=2, pady=2)
        cadre.pack(fill="both", expand=True)
        cadre.columnconfigure(0, weight=1)

        self.lbl_debit = tk.Label(cadre, text="", font=POLICE, fg=COULEUR_TEXTE,
                                  bg=COULEUR_FOND, anchor="w", justify="left")
        self.lbl_debit.grid(row=0, column=0, sticky="we", padx=(6, 10), pady=(3, 0))

        self.lbl_total = tk.Label(cadre, text="", font=POLICE_SOURDINE,
                                  fg=COULEUR_SOURDINE, bg=COULEUR_FOND,
                                  anchor="w", justify="left")
        self.lbl_total.grid(row=1, column=0, sticky="we", padx=(6, 10), pady=(0, 3))

        self.btn_jours = bouton_plat(cadre, " ≡ ", self._basculer_jours)
        self.btn_jours.grid(row=0, column=1, rowspan=2, sticky="ns",
                            padx=(0, 1), pady=2)

        self.btn_apropos = bouton_plat(cadre, " ? ", self._basculer_apropos)
        self.btn_apropos.grid(row=0, column=2, rowspan=2, sticky="ns",
                              padx=(0, 1), pady=2)

        self.btn_fermer = bouton_plat(cadre, " × ", self.quitter, COULEUR_ALERTE)
        self.btn_fermer.grid(row=0, column=3, rowspan=2, sticky="ns",
                             padx=(0, 1), pady=2)

        # Déplacement : un binding posé sur le toplevel s'applique aussi à ses
        # enfants (bindtags), donc on peut glisser depuis n'importe quel point
        # du widget. Les boutons rendent « break » et ne déclenchent pas le
        # glissement.
        r.bind("<Button-1>", self._drag_debut)
        r.bind("<B1-Motion>", self._drag_mouvement)
        for zone in (cadre, self.lbl_debit, self.lbl_total):
            zone.configure(cursor="fleur")

    # -- panneaux -------------------------------------------------------------
    def _basculer_jours(self):
        if self.panneau is not None:            # déjà ouvert : on referme
            self._panneau_ferme()
            return
        self._fermer_apropos()                  # un seul panneau à la fois
        self._rafraichir_zone()
        self.panneau = PanneauJours(self)

    def _basculer_apropos(self):
        if self.a_propos is not None:
            self._fermer_apropos()
            return
        self._panneau_ferme()
        self._rafraichir_zone()
        self.a_propos = PanneauAPropos(self)

    def _rafraichir_zone(self):
        """Relit la zone utile : moniteur branché, résolution changée, écran
        dupliqué depuis le lancement."""
        zone = zone_utile(self.racine)
        if zone != self._zone:
            self._zone = zone

    def _panneau_ferme(self):
        if self.panneau is not None:
            self.panneau.f.destroy()
            self.panneau = None

    def _fermer_apropos(self):
        if self.a_propos is not None:
            self.a_propos.f.destroy()
            self.a_propos = None

    # -- placement ------------------------------------------------------------
    def _marge_bas(self) -> int:
        """Marge interne à la zone utile ; marge de secours si elle n'a pas été
        détectée (barre des tâches ou Dock inclus dans la zone)."""
        r = self.racine
        zx, zy, zw, zh = self._zone
        if (zw, zh) == (r.winfo_screenwidth(), r.winfo_screenheight()):
            return MARGE_BAS_SECOURS
        return MARGE_BAS

    def _ancrer(self):
        r = self.racine
        r.update_idletasks()
        w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        zx, zy, zw, zh = self._zone
        if self._pos_manuelle is None:
            x = zx + (zw - w) // 2                 # centré dans la zone utile
            y = zy + zh - h - self._marge_bas()    # collé au bas de cette zone
        else:
            # Position choisie à la souris : on la conserve en la maintenant
            # dans les limites de l'écran quand la fenêtre change de taille.
            x, y = self._bornee(self._pos_manuelle[0], self._pos_manuelle[1], w, h)
            self._pos_manuelle = (x, y)
        r.geometry(f"{w}x{h}+{x}+{y}")

    def _bornee(self, x, y, w=None, h=None):
        """Ramène une position dans la zone utile : le widget ne peut s'y perdre."""
        r = self.racine
        if w is None or h is None:
            w, h = r.winfo_width(), r.winfo_height()
            if w <= 1 or h <= 1:                   # avant la 1re réalisation
                w, h = r.winfo_reqwidth(), r.winfo_reqheight()
        zx, zy, zw, zh = self._zone
        return max(zx, min(x, zx + zw - w)), max(zy, min(y, zy + zh - h))

    def _ancrer_si_besoin(self):
        r = self.racine
        r.update_idletasks()
        taille = (r.winfo_reqwidth(), r.winfo_reqheight())
        if taille != self._taille:             # la largeur change quand les Go montent
            self._taille = taille
            self._ancrer()

    # -- déplacement à la souris ----------------------------------------------
    def _drag_debut(self, evt):
        """Retient l'écart entre le curseur et le coin de la fenêtre."""
        self._drag = (evt.x_root - self.racine.winfo_x(),
                      evt.y_root - self.racine.winfo_y())

    def _drag_mouvement(self, evt):
        if self._drag is None:
            return
        dx, dy = self._drag
        x, y = self._bornee(evt.x_root - dx, evt.y_root - dy)
        self._pos_manuelle = (x, y)      # fige la position choisie
        self.racine.geometry(f"+{x}+{y}")

    # -- mémoire --------------------------------------------------------------
    def _sauvegarder(self):
        try:
            enregistrer_jours(self.jours, self._pos_manuelle)
        except OSError:
            pass                       # disque plein / droits : on n'interrompt pas
        self._derniere_sauvegarde = time.monotonic()

    # -- boucle ---------------------------------------------------------------
    def _tick(self):
        maintenant = time.monotonic()
        dt = max(maintenant - self.prev_t, 1e-6)
        c = lire_compteurs()
        if c is not None:
            recv, sent = c
            if self.prev_recv is None:
                # Première lecture exploitable : elle sert de référence et ne
                # comptabilise rien, sinon tout le trafic depuis le boot
                # serait porté au compte du jour.
                self.prev_recv, self.prev_sent = recv, sent
            else:
                d_recv = max(0, recv - self.prev_recv)   # max() : gère les resets
                d_sent = max(0, sent - self.prev_sent)

                # Assiette du tick : descendant seul, sauf si COMPTER_UPLOAD
                assiette = d_recv + (d_sent if COMPTER_UPLOAD else 0)
                jour = date.today().isoformat()
                if jour != self.jour:                    # passage de minuit
                    self._sauvegarder()                  # on fige la veille
                    self.jour = jour
                if assiette:
                    self.jours[jour] = self.jours.get(jour, 0) + assiette

                self.debit_down = LISSAGE * (d_recv / dt) + (1 - LISSAGE) * self.debit_down
                self.debit_up = LISSAGE * (d_sent / dt) + (1 - LISSAGE) * self.debit_up
                self.prev_recv, self.prev_sent = recv, sent
        self.prev_t = maintenant

        if maintenant - self._derniere_sauvegarde >= SAUVEGARDE_S:
            self._sauvegarder()

        self._rafraichir()
        self._ancrer_si_besoin()
        if self.panneau is not None:
            self.panneau.rafraichir()
        self.racine.after(INTERVALLE_MS, self._tick)

    def _rafraichir(self):
        # Assiette = volume descendant cumulé (art. 302 bis ZR), tous jours confondus.
        octets = sum(self.jours.values())
        assiette_go = octets / OCTETS_PAR_GO
        montant = taxe_de(octets)
        # Plafonnement (15 % du CA France / 2 % du CA total de l'émetteur) :
        # non déductible du seul trafic, le montant affiché est avant plafond.

        self.lbl_debit.config(
            text=f"↓ {fmt_debit(self.debit_down)}   ↑ {fmt_debit(self.debit_up)}"
        )
        self.lbl_total.config(
            text=f"Σ {fmt_go(assiette_go)}  ·  taxe {fmt_euros(montant)}",
            fg=COULEUR_ALERTE if montant > 0 else COULEUR_SOURDINE,
        )

    # -- fermeture propre -----------------------------------------------------
    def quitter(self):
        self._sauvegarder()
        self._panneau_ferme()
        self._fermer_apropos()
        self.racine.destroy()


def main():
    activer_dpi()
    if not verrouiller_instance():
        print("TaxeGigabit tourne déjà : une seule instance à la fois.",
              file=sys.stderr)
        return
    racine = tk.Tk()
    racine.title("TaxeGigabit")
    appliquer_icone(racine)
    widget = TaxeGigabit(racine)
    try:
        racine.mainloop()
    except KeyboardInterrupt:               # Ctrl+C au terminal : on sauve et sort
        widget.quitter()


if __name__ == "__main__":
    main()
