'''
Created on Nov 24, 2022

@author: graflu
'''

import pytest

from eodal.core.band import Band
from eodal.core.raster import RasterCollection

def test_raster_is_scene(get_bandstack):
    """test the is_scene attribute of RasterCollections"""

    fpath_raster = get_bandstack()
    ds = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster
    )
    assert not ds.is_scene, 'scene metadata have not been set, so it is not a scene'

    ds.scene_properties.acquisition_time = 2000
    ds.scene_properties.platform = 'test'
    assert ds.is_scene, 'scene metadata have been set, so it is a scene'
