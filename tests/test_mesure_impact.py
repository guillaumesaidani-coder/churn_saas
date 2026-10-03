"""Tests de `src/mesure_impact.py` : protocole de mesure D12 (révisée le 2026-10-03).

Données synthétiques uniquement : une sortie de `assigner_priorites` fabriquée à la main, des
issues inventées dont on connaît le résultat attendu.
"""
import json

import numpy as np
import pandas as pd
import pytest

from src.mesure_impact import (
    ACTION_TEMOIN_MOYENNE, COLONNES_SUIVI, completer_journal, consolider, graine_du_cycle,
    rapprocher_issues, resume_groupes, suivi_du_cycle, tirer_groupes_d12,
)
from src.production import ajouter_au_journal, lire_journal
from src.scoring import assigner_priorites, recommander_action


@pytest.fixture
def priorites():
    """100 comptes : 60 signalés (score >= 0,5), capacité Haute de 20, filet D14 actif."""
    rng = np.random.default_rng(0)
    resultats = pd.DataFrame({
        "client_id": [f"CLI-{i:03d}" for i in range(100)],
        "score_churn": np.round(np.r_[rng.uniform(0.5, 1.0, 60), rng.uniform(0.0, 0.5, 40)], 3),
        "perte_attendue_eur": np.round(rng.uniform(100, 10_000, 100), 0),
    })
    return assigner_priorites(resultats, seuil_d9=0.5, capacite_haute=20)


class TestTirage:
    def test_effectifs_des_groupes(self, priorites):
        out = tirer_groupes_d12(priorites, graine=1)
        haute = out[out["priorite"] == "Haute"]["groupe_D12"].value_counts().to_dict()
        assert haute == {"traite": 16, "temoin": 4}                      # 20 % de 20
        assert (out["groupe_D12"] == "renfort").sum() == 4               # autant que de témoins Haute
        moyenne_signales = out[(out["priorite"] == "Moyenne") & out["signale_D9"]]
        assert (moyenne_signales["groupe_D12"] == "temoin").sum() == round(36 * 0.10)   # 40 - 4 renforts
        assert (out.loc[out["priorite"] == "Basse", "groupe_D12"] == "hors_protocole").all()
        assert (out.loc[out["filet_D14"], "groupe_D12"] == "hors_protocole").all()

    def test_appels_constants_et_aucun_compte_haute_sans_action(self, priorites):
        out = tirer_groupes_d12(priorites, graine=1)
        appel, email = recommander_action("Haute"), recommander_action("Moyenne")
        assert (out["action_recommandee"] == appel).sum() == 20          # capacité D10 inchangée
        assert (out.loc[out["groupe_D12"] == "temoin"].query("priorite == 'Haute'")["action_recommandee"] == email).all()
        assert (out.loc[(out["priorite"] == "Moyenne") & (out["groupe_D12"] == "temoin"), "action_recommandee"]
                == ACTION_TEMOIN_MOYENNE).all()

    def test_renforts_sont_les_suivants_dans_l_ordre_de_perte(self, priorites):
        out = tirer_groupes_d12(priorites, graine=1)
        assert sorted(out.loc[out["groupe_D12"] == "renfort", "rang_perte_attendue"]) == [21, 22, 23, 24]

    def test_priorite_de_la_regle_inchangee(self, priorites):
        out = tirer_groupes_d12(priorites, graine=1)
        assert out["priorite"].equals(priorites["priorite"])

    def test_tirage_reproductible_par_cycle(self, priorites):
        g1 = tirer_groupes_d12(priorites, graine_du_cycle("2026-11"))["groupe_D12"]
        g2 = tirer_groupes_d12(priorites, graine_du_cycle("2026-11"))["groupe_D12"]
        g3 = tirer_groupes_d12(priorites, graine_du_cycle("2026-12"))["groupe_D12"]
        assert g1.equals(g2) and not g1.equals(g3)

    def test_resume_sans_donnee_par_compte(self, priorites):
        resume = resume_groupes(tirer_groupes_d12(priorites, graine=1))
        assert resume["haute_temoin"] == 4 and resume["moyenne_renfort"] == 4
        assert "CLI" not in json.dumps(resume)


class TestSuivi:
    def test_colonnes_minimales(self, priorites):
        suivi = suivi_du_cycle(tirer_groupes_d12(priorites, graine=1), "2026-11", seuil_d9=0.5)
        assert list(suivi.columns) == COLONNES_SUIVI
        assert "score_churn" not in suivi and "perte_attendue_eur" not in suivi
        assert (suivi["cycle"] == "2026-11").all()

    def test_bande_autour_du_seuil(self):
        resultats = pd.DataFrame({"client_id": list("ABCD"), "score_churn": [0.46, 0.54, 0.40, 0.60],
                                  "perte_attendue_eur": [1.0, 2.0, 3.0, 4.0]})
        out = tirer_groupes_d12(assigner_priorites(resultats, 0.5, capacite_haute=1), graine=1)
        suivi = suivi_du_cycle(out, "c", seuil_d9=0.5).set_index("client_id")
        assert suivi["bande_seuil_D12"].to_dict() == {"A": True, "B": True, "C": False, "D": False}


def suivi_fabrique():
    """Suivi écrit à la main : 10 Haute traités, 10 Haute témoins, 10 Moyenne traités, 10 Moyenne
    témoins ; 2 comptes de part et d'autre du seuil."""
    lignes = []
    for groupe, priorite, n in [("traite", "Haute", 10), ("temoin", "Haute", 10),
                                ("traite", "Moyenne", 10), ("temoin", "Moyenne", 10)]:
        lignes += [{"priorite": priorite, "groupe_D12": groupe, "signale_D9": True, "filet_D14": False,
                    "bande_seuil_D12": False} for _ in range(n)]
    lignes[20]["bande_seuil_D12"] = lignes[21]["bande_seuil_D12"] = True            # au-dessus, traités
    lignes += [{"priorite": "Basse", "groupe_D12": "hors_protocole", "signale_D9": False, "filet_D14": False,
                "bande_seuil_D12": True} for _ in range(2)]                          # au-dessous
    suivi = pd.DataFrame(lignes)
    suivi.insert(0, "client_id", [f"CLI-{i:03d}" for i in range(len(suivi))])
    suivi.insert(0, "cycle", "2026-11")
    return suivi


def issues_fabriquees(suivi):
    """Churn : 3/10 Haute traités, 5/10 Haute témoins, 4/10 Moyenne traités, 6/10 Moyenne témoins,
    1/2 sous le seuil ; le dernier compte n'a pas d'issue connue."""
    churn = [1] * 3 + [0] * 7 + [1] * 5 + [0] * 5 + [1] * 4 + [0] * 6 + [1] * 6 + [0] * 4 + [1, 0]
    issues = pd.DataFrame({"client_id": suivi["client_id"], "churn": churn})
    return issues.iloc[:-1]


class TestRapprochement:
    def test_agregats(self):
        suivi = suivi_fabrique()
        agregats = rapprocher_issues(suivi, issues_fabriquees(suivi))
        assert agregats["comptes_rapproches"] == 41 and agregats["comptes_sans_issue"] == 1
        assert agregats["groupes"]["haute_traite"] == {"comptes": 10, "churn": 3, "taux_churn": 0.3}
        assert agregats["groupes"]["moyenne_temoin"]["taux_churn"] == 0.6
        assert agregats["ecarts"]["B_gain_appel_sur_email"]["ecart"] == pytest.approx(0.2)
        assert agregats["ecarts"]["D_effet_email"]["ecart"] == pytest.approx(0.2)
        borne_basse, borne_haute = agregats["ecarts"]["B_gain_appel_sur_email"]["ic95"]
        assert borne_basse < 0.2 < borne_haute
        assert agregats["rappel_reel"] == round(18 / 19, 4)   # 18 départs signalés sur 19

    def test_aucune_donnee_par_compte(self):
        suivi = suivi_fabrique()
        assert "CLI" not in json.dumps(rapprocher_issues(suivi, issues_fabriquees(suivi)))

    def test_groupe_vide_donne_un_ecart_nul(self):
        suivi = suivi_fabrique()
        agregats = rapprocher_issues(suivi[suivi["priorite"] != "Basse"], issues_fabriquees(suivi))
        assert agregats["ecarts"]["C_effet_email_au_seuil"] == {"ecart": None, "ic95": None}

    def test_consolidation_additionne_les_effectifs(self):
        suivi = suivi_fabrique()
        agregats = rapprocher_issues(suivi, issues_fabriquees(suivi))
        bilan = consolider([agregats, agregats])
        assert bilan["cycles"] == 2
        assert bilan["groupes"]["haute_temoin"] == {"comptes": 20, "churn": 10, "taux_churn": 0.5}
        assert bilan["ecarts"]["B_gain_appel_sur_email"]["ecart"] == pytest.approx(0.2)
        # Deux fois plus de comptes : intervalle plus étroit.
        largeur = lambda e: e["ic95"][1] - e["ic95"][0]  # noqa: E731
        assert largeur(bilan["ecarts"]["B_gain_appel_sur_email"]) < largeur(agregats["ecarts"]["B_gain_appel_sur_email"])

    def test_sans_colonnes_facultatives(self):
        suivi = suivi_fabrique()
        agregats = rapprocher_issues(suivi, issues_fabriquees(suivi))
        assert agregats["recette_D15"] is None and agregats["ecarts_protocole"] is None
        assert agregats["declencheur_rappel_reel"] == {"actif": False, "seuil": 0.75}   # rappel 0,95

    def test_recette_d15_et_ecarts_au_protocole(self):
        suivi = suivi_fabrique()
        issues = issues_fabriquees(suivi)
        # Valeur réelle : 1 000 € par compte, 100 000 € pour les Haute ; un témoin Haute appelé quand même.
        issues["valeur_vie_client_eur"] = np.where(suivi["priorite"].iloc[:-1] == "Haute", 100_000.0, 1_000.0)
        issues["ecart_protocole"] = 0
        issues.loc[10, "ecart_protocole"] = 1
        agregats = rapprocher_issues(suivi, issues)
        r = agregats["recette_D15"]
        # Partis : 8 Haute (800 000 €) et 11 autres (11 000 €) -> (b') = 800 / 811
        assert r["perte_reelle_haute_eur"] == 800_000 and r["perte_reelle_totale_eur"] == 811_000
        assert r["b_part_perte_captee_haute"] == round(800 / 811, 4) and r["b_respecte"]
        # Forte perte (>= 3e quartile des partis, 100 000 €) : les 8 partis Haute, tous couverts
        assert (r["partis_forte_perte"], r["forte_perte_couverts"], r["c_respecte"]) == (8, 8, True)
        assert agregats["ecarts_protocole"] == {"total": 1, "par_groupe": {
            "haute_traite": 0, "haute_temoin": 1, "renfort": 0, "moyenne_traite": 0, "moyenne_temoin": 0,
            "seuil_dessus": 0, "seuil_dessous": 0}}
        bilan = consolider([agregats, agregats])
        assert bilan["recette_D15"]["b_part_perte_captee_haute"] == r["b_part_perte_captee_haute"]
        assert bilan["ecarts_protocole"] == {"total": 2}

    def test_declencheur_rappel_reel(self):
        suivi = suivi_fabrique()
        suivi["signale_D9"] = False            # aucun départ signalé : rappel réel nul
        agregats = rapprocher_issues(suivi, issues_fabriquees(suivi))
        assert agregats["rappel_reel"] == 0.0 and agregats["declencheur_rappel_reel"]["actif"]

    def test_journal_complete_sans_changer_l_ordre(self, tmp_path):
        journal = tmp_path / "journal_scores.jsonl"
        for cycle in ["2026-11", "2026-12"]:
            ajouter_au_journal(journal, {"cycle": cycle})
        completer_journal(journal, "2026-11", {"rappel_reel": 0.8})
        entrees = lire_journal(journal)
        assert [e["cycle"] for e in entrees] == ["2026-11", "2026-12"]
        assert entrees[0]["issues"] == {"rappel_reel": 0.8} and "issues" not in entrees[1]
        with pytest.raises(KeyError):
            completer_journal(journal, "2027-01", {})
