'''
Created on Nov 25, 2022

@author: graflu
'''

import pytest

from eodal.core.raster import RasterCollection

def test_raster_copy(get_bandstack):
    """test copy() method of RasterCollection objects"""
    fpath_raster = get_bandstack()
    rcoll = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster,
        band_aliases=['a','b','c','d','e','f','g','h','i','j']
    )
    rcoll_copy = rcoll.copy()

    assert rcoll_copy.band_names == rcoll.band_names, 'band names differ'
    assert rcoll_copy.band_aliases == rcoll.band_aliases, 'band aliases differ'
    assert (rcoll_copy.band_summaries() == rcoll.band_summaries()).all().all(), \
        'band statistics differ'
    assert rcoll_copy['a'].crs == rcoll['a'].crs, 'Band CRS differ'
    assert rcoll_copy['b'].get_attributes() == rcoll['b'].get_attributes(), \
        'Band attributes differ'
