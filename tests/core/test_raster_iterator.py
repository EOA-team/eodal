'''
Created on Nov 20, 2022

@author: graflu
'''

import pytest

from eodal.core.band import Band
from eodal.core.raster import RasterCollection

def test_raster_iterator(get_bandstack):
    fpath_raster = get_bandstack()
    ds = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster
    )
    band_names = ds.band_names

    idx = 0
    for band_name, band_obj in ds:
        assert band_name == band_names[idx], 'wrong band name returned'
        assert isinstance(band_obj, Band), 'no band object returned'
        assert band_obj.band_name == band_name, 'band names do not match'
