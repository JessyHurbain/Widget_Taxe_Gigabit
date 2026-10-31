"""Tests des calculs et de la mémoire d'état.

Aucune fenêtre n'est ouverte : le module est importé pour ses fonctions pures,
Tk n'étant tiré qu'à l'import (pas de Tk() ici). Les tests tournent donc sans
serveur graphique, y compris sur un runner de CI.
"""

import importlib.util
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def charger_module():
    spec = importlib.util.spec_from_file_location(
        "taxe_gigabit", RACINE / "taxe_gigabit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tg = charger_module()


@pytest.fixture
def etat(tmp_path, monkeypatch):
    """Redirige le fichier d'état vers un dossier temporaire."""
    chemin = tmp_path / "etat.json"
    monkeypatch.setattr(tg, "FICHIER_ETAT", str(chemin))
    return chemin


# -- barème -------------------------------------------------------------------

def test_taxe_nulle_sans_volume():
    assert tg.taxe_de(0) == 0.0


def test_taxe_un_gigaoctet():
    assert tg.taxe_de(tg.OCTETS_PAR_GO) == pytest.approx(0.055)


def test_taxe_gta_vi():
    """210 Go annoncés sur PS5 : cohérent avec le README (11,55 €)."""
    assert tg.taxe_de(210 * tg.OCTETS_PAR_GO) == pytest.approx(11.55)


def test_taxe_ignore_un_volume_negatif():
    assert tg.taxe_de(-5 * tg.OCTETS_PAR_GO) == 0.0


def test_assiette_legale_exclut_l_upload():
    """Le barème ne compte que le descendant : le réglage ne doit pas dériver."""
    assert tg.COMPTER_UPLOAD is False


# -- mise en forme ------------------------------------------------------------

def test_fmt_debit_change_d_unite():
    assert tg.fmt_debit(0).strip() == "0,00 o/s"
    assert tg.fmt_debit(1024).strip() == "1,00 Ko/s"
    assert tg.fmt_debit(1024 ** 2).strip() == "1,00 Mo/s"


def test_fmt_debit_garde_une_largeur_fixe():
    largeurs = {len(tg.fmt_debit(v)) for v in (0, 999, 1024, 5 * 1024 ** 2)}
    assert len(largeurs) == 1


def test_fmt_go_virgule_decimale():
    assert tg.fmt_go(12.407) == "12,407 Go"


def test_fmt_euros_fin_supprime_les_zeros_inutiles():
    assert tg.fmt_euros_fin(11.55) == "11,55 €"
    assert tg.fmt_euros_fin(0.000275) == "0,000275 €"
    assert tg.fmt_euros_fin(0) == "0 €"


# -- mémoire d'état -----------------------------------------------------------

def test_charger_jours_sans_fichier(etat):
    assert tg.charger_jours() == {}


def test_charger_jours_json_invalide(etat):
    etat.write_text("{ ceci n'est pas du json", encoding="utf-8")
    assert tg.charger_jours() == {}


def test_charger_jours_structure_inattendue(etat):
    etat.write_text(json.dumps({"jours": [1, 2, 3]}), encoding="utf-8")
    assert tg.charger_jours() == {}


def test_une_entree_corrompue_ne_perd_pas_le_reste(etat):
    """Le point sensible : avant, une valeur illisible vidait tout l'historique."""
    etat.write_text(json.dumps({"version": 1, "jours": {
        "2026-10-01": 5_000_000_000,
        "2026-10-02": "abc",
        "2026-10-03": None,
        "2026-10-04": 0,
        "2026-10-05": 1_500_000_000,
    }}), encoding="utf-8")
    assert tg.charger_jours() == {
        "2026-10-01": 5_000_000_000,
        "2026-10-05": 1_500_000_000,
    }


def test_aller_retour_enregistrement(etat):
    jours = {"2026-10-30": 12_400_000_000, "2026-10-31": 8_100_000_000}
    tg.enregistrer_jours(jours)
    assert tg.charger_jours() == jours
    assert etat.exists()
    assert not Path(str(etat) + ".tmp").exists()   # écriture atomique terminée


def test_enregistrement_cree_le_dossier(etat):
    etat.parent.joinpath("sous-dossier").mkdir()
    tg.FICHIER_ETAT = str(etat.parent / "sous-dossier" / "etat.json")
    tg.enregistrer_jours({"2026-10-31": 1})
    assert tg.charger_jours() == {"2026-10-31": 1}
