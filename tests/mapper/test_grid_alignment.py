'''
Ensure that all scenes in a SceneCollection have the same spatial
extent, pixel size and number of rows and columns. We test this
behavior for Sentinel-2 scenes at the boundary of two UTM zones.
'''

import geopandas as gpd
import pytest

from datetime import datetime
from eodal.config import get_settings
from eodal.core.raster import RasterCollection
from eodal.core.sensors import Sentinel2
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

settings = get_settings()


def test_grid_alignment(get_polygons_utm_zones):
    """test grid alignment for Sentinel-2"""

    settings.USE_STAC = True

    time_start = datetime(2018, 3, 2)
    time_end = datetime(2018, 4, 6)
    metadata_filters = [
        Filter('cloudy_pixel_percentage', '<', 70),
        Filter('processing_level', '==', 'Level-2A')
    ]
    feature = Feature.from_geoseries(
        gds=gpd.read_file(get_polygons_utm_zones()).geometry)
    mapper_configs = MapperConfigs(
        collection='sentinel2-msi',
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )

    mapper = Mapper(mapper_configs)
    mapper.query_scenes()

    def resample(ds: RasterCollection, **kwargs):
        return ds.resample(inplace=False, **kwargs)

    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {
            'band_selection': ['red', 'red_edge_1'],
            'apply_scaling': False
        },
        'scene_modifier': resample,
        'scene_modifier_kwargs': {'target_resolution': 10}
    }
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    # all scenes should have the same extent and, since, we resampled
    # all bands to a common spatial extent, the same pixel size and number
    # of rows and columns
    scoll = mapper.data

    pixres_x, pixres_y, ulx, uly, nrows, ncols = [], [], [], [], [], []
    for _, scene in scoll:
        for _, band in scene:
            geo_info = band.geo_info
            pixres_x.append(geo_info.pixres_x)
            pixres_y.append(geo_info.pixres_y)
            ulx.append(geo_info.ulx)
            uly.append(geo_info.uly)
            nrows.append(band.nrows)
            ncols.append(band.ncols)

    assert len(set(pixres_x)) == 1
    assert pixres_x[0] == 10
    assert len(set(pixres_y)) == 1
    assert pixres_y[0] == -10
    assert len(set(ulx)) == 1
    assert len(set(uly)) == 1
    assert len(set(nrows)) == 1
    assert len(set(ncols)) == 1

    # this should also work when the bands are not bandstacked
    # i.e., have a different pixel size
    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {
            'band_selection': ['red', 'red_edge_1'],
            'apply_scaling': False
        }
    }
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    scoll = mapper.data

    band_names = scoll[scoll.timestamps[0]].band_names
    # the upper left corner must be always the same
    ulx, uly = [], []
    for band_name in band_names:
        pixres_x, pixres_y, nrows, ncols = [], [], [], []
        for _, scene in scoll:
            band = scene[band_name]
            geo_info = band.geo_info
            pixres_x.append(geo_info.pixres_x)
            pixres_y.append(geo_info.pixres_y)
            ulx.append(geo_info.ulx)
            uly.append(geo_info.uly)
            nrows.append(band.nrows)
            ncols.append(band.ncols)

        assert len(set(pixres_x)) == 1
        assert len(set(pixres_y)) == 1
        assert len(set(nrows)) == 1
        assert len(set(ncols)) == 1
        # only the red band should have a spatial resolution of 10 m
        # as we did not resample the 20 m bands
        if band_name == 'B04':
            assert pixres_x[0] == 10.
            assert pixres_y[0] == -10.
        else:
            assert pixres_x[0] == 20.
            assert pixres_y[0] == -20.

    assert len(set(ulx)) == 1
    assert len(set(uly)) == 1
