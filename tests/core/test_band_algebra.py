
import pytest
import numpy as np

def test_band_algrebra_scalar(get_test_band):
    """test algebraic operations using scalar values on Bands"""
    band = get_test_band()
    scalar = 2.

    # test different operators using scalar on the left-hand side
    band_add = band + scalar
    assert (band_add.values - band.values == scalar).all(), 'wrong result'
    band_sub = band - scalar
    assert (band_sub.values - band.values == -scalar).all(), 'wrong result'
    band_mul = band * scalar
    assert (band_mul.values / band.values == scalar).all(), 'wrong result'
    band_div = band / scalar
    assert (band_div.values * scalar == band.values).all(), 'wrong result'
    band_pow = band**scalar
    assert (np.sqrt(band_pow.values) == band.values).all(), 'wrong results'

    # test comparison operators (band <-> band)
    band_eq = band == scalar
    assert not band_eq.values.all(), 'wrong result'
    band_gt = band > scalar
    assert band_gt.values.all(), 'wrong result'
    band_ge = band >= scalar
    assert band_ge.values.all(), 'wrong_result'
    band_lt = band < scalar
    assert not band_lt.values.all(), 'wrong result'
    band_le = band <= scalar
    assert not band_le.values.all(), 'wrong result'

def test_band_algebra_band(get_test_band):
    """test algebraic operations using Band values on Bands"""
    band = get_test_band()
    other = get_test_band()

    band_add = band + other
    assert (band_add.values - band.values == band.values).all(), 'wrong result'
    band_sub = band - other
    assert (band_sub.values == 0).all(), 'wrong result'
    band_mul = band * other
    assert (band_mul.values == band.values * other.values).all(), 'wrong result'
    band_div = band / other
    assert band_div.values.max() == band_div.values.min() == band_div.values.mean() == 1., \
        'wrong result'
    band_pow = band**other
    assert (band_pow.values == band.values**other.values).all(), 'wrong results'

    # test comparison operators (band <-> band)
    band_eq = band == other
    assert band_eq.values.all(), 'wrong result'
    band_gt = band > band_sub
    assert band_gt.values.all(), 'wrong result'
    band_ge = band >= band
    assert band_ge.values.all(), 'wrong_result'
    band_lt = band < band_sub
    assert not band_lt.values.all(), 'wrong result'
    band_le = band <= band_sub
    assert not band_le.values.all(), 'wrong result'