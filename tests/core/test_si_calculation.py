import pytest

from eodal.config import get_settings
from eodal.core.sensors import Sentinel2

settings = get_settings()
settings.USE_STAC = False

@pytest.mark.parametrize('apply_scaling', [False, True])
def test_sentinel2_vi(get_s2_safe_l2a, get_polygons_2, apply_scaling):

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
        