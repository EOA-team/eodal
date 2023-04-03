
import pytest
import numpy

from eodal.core.raster import RasterCollection

def test_raster_algebra_scalar(get_bandstack):
    """test algebraic operations using scalar values on RasterCollections"""
    fpath = get_bandstack()
    rcoll = RasterCollection.from_multi_band_raster(fpath)
    scalar = 2

    # arithmetic operators
    rcoll_add = rcoll + scalar
    assert (rcoll_add.get_values() == rcoll.get_values() + scalar).all(), 'wrong result'
    rcoll_sub = rcoll - scalar
    assert (rcoll_sub.get_values() == rcoll.get_values() - scalar).all(), 'wrong result'
    rcoll_mul = rcoll * scalar
    assert (rcoll_mul.get_values() == rcoll.get_values() * scalar).all(), 'wrong result'
    rcoll_div = rcoll / scalar
    assert (rcoll_div.get_values() == rcoll.get_values() / scalar).all(), 'wrong result'
    rcoll_pow = rcoll**scalar
    assert (rcoll_pow.get_values() == rcoll.get_values() ** scalar).all(), 'wrong result'

    # flip order
    rcoll_add = scalar + rcoll
    assert (rcoll_add.get_values() == rcoll.get_values() + scalar).all(), 'wrong result'
    rcoll_sub = scalar - rcoll
    assert (rcoll_sub.get_values() == scalar - rcoll.get_values()).all(), 'wrong result'
    rcoll_mul = scalar * rcoll
    assert (rcoll_mul.get_values() == rcoll.get_values() * scalar).all(), 'wrong result'
    rcoll_div = scalar / rcoll
    assert (rcoll_div.get_values() == scalar / rcoll.get_values()).all(), 'wrong result'
    rcoll_pow = scalar**rcoll
    assert (rcoll_pow.get_values() == scalar ** rcoll.get_values()).all(), 'wrong result'

    # comparison operators
    rcoll_eq = rcoll == scalar
    assert not rcoll_eq.get_values().all(), 'wrong results'
    rcoll_gt = rcoll > scalar
    assert rcoll_gt.get_values().any(), 'wrong results'
    rcoll_ge = rcoll >= scalar
    assert rcoll_ge.get_values().any(), 'wrong results'
    rcoll_lt = rcoll < scalar
    assert rcoll_lt.get_values().any(), 'wrong results'
    rcoll_le = rcoll <= scalar
    assert rcoll_le.get_values().any(), 'wrong results'

    # flip order
    rcoll_eq_l = rcoll == scalar
    rcoll_eq_r = scalar == rcoll
    assert rcoll_eq_l == rcoll_eq_r, 'order must not matter'
    rcoll_ne_l = rcoll != scalar
    rcoll_ne_r = scalar != rcoll
    assert rcoll_ne_l == rcoll_ne_r, 'order must not matter'
    rcoll_gt_l = rcoll > scalar
    rcoll_gt_r = scalar > rcoll
    assert rcoll_gt_l.get_values().any(), 'wrong result'
    assert rcoll_gt_r.get_values().any(), 'wrong result'
    assert (rcoll_gt_l.get_values() != rcoll_gt_r.get_values()).all(), 'results must not be the same'
    rcoll_ge_l = rcoll >= scalar
    rcoll_ge_r = scalar >= rcoll
    assert rcoll_ge_l.get_values().any(), 'wrong result'
    assert rcoll_ge_r.get_values().any(), 'wrong result'
    assert (rcoll_ge_l.get_values() != rcoll_ge_r.get_values()).all(), 'results must not be the same'
    rcoll_lt_l = rcoll < scalar
    rcoll_lt_r = scalar < rcoll
    assert rcoll_lt_l.get_values().any(), 'wrong result'
    assert rcoll_lt_r.get_values().any(), 'wrong result'
    assert (rcoll_lt_l.get_values() != rcoll_lt_r.get_values()).all(), 'results must not be the same'
    rcoll_le_l = rcoll <= scalar
    rcoll_le_r = scalar <= rcoll
    assert rcoll_le_l.get_values().any(), 'wrong result'
    assert rcoll_le_r.get_values().any(), 'wrong result'
    assert (rcoll_le_l.get_values() != rcoll_le_r.get_values()).all(), 'results must not be the same'
    

def test_raster_algebra_band_and_raster(get_bandstack):
    """test algebraic operations using Bands and Rasters on RasterCollections"""
    fpath = get_bandstack()
    rcoll = RasterCollection.from_multi_band_raster(fpath)
    band = rcoll['B02'].copy()

    # RasterCollection <-> Band
    rcoll_add = rcoll + band
    assert (rcoll_add.get_values() == rcoll.get_values() + band.values).all(), 'wrong result'
    rcoll_sub = rcoll - band
    assert (rcoll_sub.get_values() == rcoll.get_values() - band.values).all(), 'wrong result'
    rcoll_mul = rcoll * band
    assert (rcoll_mul.get_values() == rcoll.get_values() * band.values).all(), 'wrong result'
    rcoll_pow = rcoll**band
    assert (rcoll_pow.get_values() == rcoll.get_values() ** band.values).all(), 'wrong result'

    rcoll_eq = rcoll == band
    assert rcoll_eq.get_values().any(), 'wrong results'
    assert rcoll_eq['B02'].values.all(), 'wrong results'
    rcoll_gt = rcoll > band
    assert rcoll_gt.get_values().any(), 'wrong results'
    rcoll_ge = rcoll >= band
    assert rcoll_ge.get_values().any(), 'wrong results'
    rcoll_lt = rcoll < band
    assert rcoll_lt.get_values().any(), 'wrong results'
    rcoll_le = rcoll <= band
    assert rcoll_le.get_values().any(), 'wrong results'

    # RasterCollection <-> RasterCollection
    other = RasterCollection.from_multi_band_raster(fpath)
    rcoll_add = rcoll + other
    assert (rcoll_add.get_values() == rcoll.get_values() + other.get_values()).all(), 'wrong result'
    rcoll_sub = rcoll - other
    assert (rcoll_sub.get_values() == rcoll.get_values() - other.get_values()).all(), 'wrong result'
    rcoll_mul = rcoll * other
    assert (rcoll_mul.get_values() == rcoll.get_values() * other.get_values()).all(), 'wrong result'
    rcoll_pow = rcoll**other
    assert (rcoll_pow.get_values() == rcoll.get_values() ** other.get_values()).all(), 'wrong result'

    rcoll_eq = rcoll == other
    assert rcoll_eq.get_values().all(), 'wrong result'
    rcoll_ne = rcoll != other
    assert not rcoll_ne.get_values().any(), 'wrong result'
    