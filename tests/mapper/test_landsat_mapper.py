'''
Tests for the Mapper class for Sentinel-2.

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
import numpy as np
import pytest

from datetime import datetime
from shapely.geometry import box, Polygon

from eodal.config import get_settings
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.core.sensors import Landsat
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

Settings = get_settings()


def preprocess_landsat_scene(
        ds: Landsat
) -> Landsat:
    """
    Mask clouds and cloud shadows in a Landsat scene based
    on the 'qa_pixel' band.

    :param ds:
        Landsat scene before cloud mask applied.
    :return:
        Landsat scene with clouds and cloud shadows masked.
    """
    ds.mask_clouds_and_shadows(inplace=True)
    return ds


@pytest.mark.parametrize(
    'collection,time_start,time_end,geom,metadata_filters,apply_scaling',
    [(
        'landsat-c2-l2',
        datetime(2022,7,1),
        datetime(2022,7,15),
        Polygon(
            [[7.04229, 47.01202],
            [7.08525, 47.01202],
            [7.08525, 46.96316],
            [7.04229, 46.96316],
            [7.04229, 47.01202]]
        ),
        [Filter('eo:cloud_cover','<', 80)],
        False
    ),(
        'landsat-c2-l2',
        datetime(2022,7,1),
        datetime(2022,7,15),
        Polygon(
            [[7.04229, 47.01202],
            [7.08525, 47.01202],
            [7.08525, 46.96316],
            [7.04229, 46.96316],
            [7.04229, 47.01202]]
        ),
        [Filter('eo:cloud_cover','<', 80)],
        True
    ),
    (
        'landsat-c2-l1',
        datetime(1972, 9, 1),
        datetime(1972, 10, 31),
        box(*[8.4183, 47.2544, 8.7639, 47.5176]),
        [Filter('eo:cloud_cover','<', 80)],
        False
    )
    ]
)
def test_landsat_mapper(
        collection, time_start, time_end, geom, metadata_filters,
        apply_scaling):
    """
    Test the mapper class for handling Landsat collection 2 data
    (level 1 and 2).
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

    scene_kwargs = {
        'scene_constructor': Landsat.from_usgs,
        'scene_constructor_kwargs': {
            'band_selection': ['red', 'nir08'],
            'read_qa': True,
            'apply_scaling': apply_scaling
        },
        'scene_modifier': preprocess_landsat_scene
    }
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    assert isinstance(mapper.data, SceneCollection), 'expected a SceneCollection'
    assert mapper.metadata.target_epsg.nunique() == 1, 'there must not be more than a single target EPSG'
    scenes_crs = [x['red'].crs.to_epsg() for _, x in mapper.data]
    assert (scenes_crs == mapper.metadata.target_epsg.unique()[0]).all(), \
        'all scenes must be projected into the target EPSG'
    assert mapper.metadata.shape[0] == len(mapper.data), \
        'mis-match between length of metadata and data'

    for _, scene in mapper.data:
        dtype = scene['red'].values.dtype
        if apply_scaling:
            assert dtype in [np.float32, np.float64]
        else:
            assert dtype in [np.uint8, np.uint16]
