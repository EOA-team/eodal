import pytest

import numpy as np

from eodal.config import get_settings
from eodal.core.spectral_indices import SpectralIndices
from eodal.core.sensors import Sentinel2


def test_si_list():

    si_list = SpectralIndices().get_si_list()
    assert len(si_list) > 0, 'too few SIs found'
    assert 'NDVI' in si_list, 'expected at least to find the NDVI'


def test_si_bandmapping(get_s2_safe_l2a, get_polygons_2):
    settings = get_settings()
    settings.USE_STAC = False

    s2_dir = get_s2_safe_l2a()
    vector_features = get_polygons_2()

    s2 = Sentinel2().from_safe(
        in_dir=s2_dir,
        vector_features=vector_features
    )

    # calculate default NDVI using band 8 (nir_1)
    ndvi_b08 = s2.calc_si('ndvi')

    # calculate the NDVI using band 8A instead
    # this should fail because Band 8A is still in 20 m spatial resolution
    # while the red band is 10 m.
    with pytest.raises(ValueError):
        s2.calc_si('ndvi', band_mapping={'nir_1': 'nir_2'})
    # but it should succeed if we resample the bands to 10 m
    s2.resample(target_resolution=10, inplace=True)
    ndvi_b8a = s2.calc_si('ndvi', band_mapping={'nir_1': 'nir_2'})

    assert (ndvi_b08 != ndvi_b8a).any(), \
        'B08 and B8A should not yield the exactly same result'
    assert not (ndvi_b08 == ndvi_b8a).all(), \
        'B08 and B8A should not yield the exactly same result'

    assert np.min(ndvi_b08) >= -1 and np.min(ndvi_b8a) >= -1, \
        'implausible NDVI values encountered'
    assert np.max(ndvi_b08) <= 1 and np.max(ndvi_b8a) <= 1, \
        'implausible NDVI values encountered'


@pytest.mark.parametrize('apply_scaling', [False, True])
def test_sentinel2_vi(get_s2_safe_l2a, get_polygons_2, apply_scaling):

    settings = get_settings()
    settings.USE_STAC = False

    s2_dir = get_s2_safe_l2a()
    vector_features = get_polygons_2()

    s2 = Sentinel2().from_safe(
        in_dir=s2_dir,
        vector_features=vector_features,
        apply_scaling=apply_scaling
    )

    ndvi = s2.calc_si('NDVI')
    assert 0 <= ndvi.max() <= 1, 'wrong scale for NDVI'
    assert -1 <= ndvi.min() <= 0, 'expected a negative number here'
    assert 0 <= ndvi.mean() <= 1, 'expected a positive number here'

    evi = s2.calc_si('EVI')
    assert 0 <= evi.max() <= 1, 'wrong scale for EVI'
    assert -1 <= evi.min() <= 0, 'expected a negative number here'
    assert 0 <= evi.mean() <= 1, 'expected a positive number here'
