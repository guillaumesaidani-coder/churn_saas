"""Tests unitaires de `src/drift.py`, portés à l'identique de `py-init/ml/tests/test_drift.py`
(le calcul PSI/KS est générique, aucune adaptation n'était nécessaire) : un PSI quasi nul sur
une distribution inchangée, un PSI élevé sur une dérive franche, et les bins figés sur la
référence seule.
"""
import numpy as np
import pandas as pd

from src.drift import drift_table, ks_pvalue, psi, reference_bin_edges

rng = np.random.default_rng(42)


def test_psi_near_zero_on_identical_distribution():
    reference = pd.Series(rng.normal(50, 5, 2000))
    current = pd.Series(rng.normal(50, 5, 2000))
    assert psi(reference, current) < 0.05


def test_psi_high_on_shifted_distribution():
    reference = pd.Series(rng.normal(50, 5, 2000))
    current = pd.Series(rng.normal(58, 5, 2000))
    assert psi(reference, current) > 0.25


def test_ks_pvalue_low_on_shifted_distribution():
    reference = pd.Series(rng.normal(50, 5, 2000))
    current = pd.Series(rng.normal(58, 5, 2000))
    assert ks_pvalue(reference, current) < 0.01


def test_ks_pvalue_high_on_identical_distribution():
    reference = pd.Series(rng.normal(50, 5, 2000))
    current = pd.Series(rng.normal(50, 5, 2000))
    assert ks_pvalue(reference, current) > 0.05


def test_bin_edges_are_frozen_on_reference_only():
    reference = pd.Series(rng.normal(50, 5, 2000))
    edges_before = reference_bin_edges(reference)
    _ = psi(reference, pd.Series(rng.normal(200, 50, 500)))
    edges_after = reference_bin_edges(reference)
    np.testing.assert_array_equal(edges_before, edges_after)


def test_psi_is_finite_with_missing_values():
    reference = pd.Series([1.0, 2.0, 3.0, np.nan, 4.0, 5.0] * 50)
    current = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, np.nan] * 50)
    value = psi(reference, current)
    assert np.isfinite(value)


def test_drift_table_has_one_row_per_feature():
    reference = pd.DataFrame({
        "anciennete_mois": rng.normal(24, 6, 500),
        "csat": rng.normal(4, 0.5, 500),
    })
    current = pd.DataFrame({
        "anciennete_mois": rng.normal(24, 6, 500),
        "csat": rng.normal(4, 0.5, 500),
    })
    table = drift_table(reference, current, ["anciennete_mois", "csat"])
    assert list(table["feature"]) == ["anciennete_mois", "csat"]
    assert {"psi", "ks_pvalue"}.issubset(table.columns)
