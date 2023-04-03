'''
Tests for the filter class.

.. versionadded:: 0.2.0

Copyright (C) 2023 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import geopandas as gpd
import pytest

from datetime import datetime
from shapely.geometry import Polygon

from eodal.config import get_settings
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.core.sensors import Sentinel2
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

Settings = get_settings()

@pytest.mark.parametrize(
    'collection,time_start,time_end,geom,metadata_filters',
    [(
        'sentinel2-msi',
        datetime(2022,7,1),
        datetime(2022,7,15),
        Polygon(
            [[7.04229, 47.01202],
            [7.08525, 47.01202],
            [7.08525, 46.96316],
            [7.04229, 46.96316],
            [7.04229, 47.01202]]
        ),
        [Filter('cloudy_pixel_percentage','<', 80), Filter('processing_level', '==', 'Level-2A')],
    ),]
)
def test_sentinel2_mapper(collection, time_start, time_end, geom, metadata_filters):
    """
    Test the mapper class for handling Sentinel-2 data including mosaicing data
    from two different Sentinel-2 tiles
    """
    Settings.USE_STAC = True
    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=4326,
        attributes={'id': 1}
    )
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()
    assert isinstance(mapper.metadata, gpd.GeoDataFrame), 'expected a GeoDataFrame'
    assert not mapper.metadata.empty, 'metadata must not be empty'

    def resample(ds: RasterCollection, **kwargs):
        return ds.resample(inplace=False, **kwargs)

    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {'band_selection': ['B04', 'B08']},
        'scene_modifier': resample,
        'scene_modifier_kwargs': {'target_resolution': 10}
    }
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    assert isinstance(mapper.data, SceneCollection), 'expected a SceneCollection'
    assert mapper.metadata.target_epsg.nunique() == 1, 'there must not be more than a single target EPSG'
    scenes_crs = [x['red'].crs.to_epsg() for _, x in mapper.data]
    assert (scenes_crs == mapper.metadata.target_epsg.unique()[0]).all(), \
        'all scenes must be projected into the target EPSG'
    assert mapper.metadata.shape[0] == len(mapper.data), \
        'mis-match between length of metadata and data'
