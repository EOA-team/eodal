
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
    assert ((band_pow.values)**(1/scalar) == band.values).all(), 'wrong results'

    # flip order (scalar on the right-hand side) 
    band_add = scalar + band
    assert (band_add.values - band.values == scalar).all(), 'wrong result'
    band_sub = scalar - band
    assert (band_sub.values + band.values == scalar).all(), 'wrong result'
    band_mul = scalar * band
    assert (band_mul.values / band.values == scalar).all(), 'wrong result'
    band_div = scalar / band
    assert (band_div.values * band.values - scalar < 1e-10).all(), 'wrong result'
    band_pow = scalar**band
    assert (band_pow.values == scalar**band.values).all(), 'wrong results'

    # comparison operators: scalar <-> band (both sides)
    band_eq_r = scalar == band
    band_eq_l = band == scalar
    assert (band_eq_l == band_eq_r).values.all(), 'order must not matter'
    band_ne_r = scalar != band
    band_ne_l = band != scalar
    assert (band_ne_l == band_ne_r).values.all(), 'order must not matter'
    band_gt_r = scalar > band
    band_gt_l = band < scalar
    assert not band_gt_r.values.all() and not band_gt_l.values.all(), 'wrong result'
    band_ge_r = scalar >= band
    band_ge_l = band <= scalar
    assert not band_ge_r.values.all() and not band_ge_l.values.all(), 'wrong result'
    band_lt_r = scalar < band
    band_lt_l = band > scalar
    assert band_lt_r.values.all() and band_lt_l.values.all(), 'wrong result'
    band_le_r = scalar <= band
    band_le_l = band >= scalar
    assert band_le_r.values.all() and band_le_l.values.all(), 'wrong result'

    # test comparison operators (band <-> band)
    band_eq = band == scalar
    assert not band_eq.values.all(), 'wrong result'
    band_ne = band != scalar
    assert band_ne.values.any(), 'wrong result'
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

    # flip order
    band_add = other + band
    assert (band_add.values - band.values == band.values).all(), 'wrong result'
    band_sub = other - band
    assert (band_sub.values == 0).all(), 'wrong result'
    band_mul = other * band
    assert (band_mul.values == band.values * other.values).all(), 'wrong result'
    band_div = other / band
    assert band_div.values.max() == band_div.values.min() == band_div.values.mean() == 1., \
        'wrong result'
    band_pow = other**band
    assert (band_pow.values == other.values**band.values).all(), 'wrong results'

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
