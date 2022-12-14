'''
Created on Dec 14, 2022

@author: graflu
'''

import pytest

from datetime import datetime
from shapely.geometry import Point, Polygon

from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import MapperConfigs, Mapper

def test_mapper_configs(tmppath):

    # construct a Feature
    collection = 'sentinel2-msi-l2a'
    geom = Point([49,11])
    epsg = 4326
    name = 'Test Point'
    attributes = {'this': 'is a test', 'a': 123}
    feature = Feature(name, geom, epsg, attributes)

    # define further search criteria
    time_start = datetime(2022,12,1)
    time_end = datetime.now()
    metadata_filters = [
        Filter('cloudy_pixel_percentage', '<30'), Filter('snow_ice_percentage', '<10')
    ]

    mapper_configs = MapperConfigs(collection, feature, time_start, time_end, metadata_filters)
    fpath = tmppath.joinpath('test.yml')
    mapper_configs.to_yaml(fpath)

    mapper_configs_rl = MapperConfigs.from_yaml(fpath)
    assert mapper_configs.feature.name == mapper_configs_rl.feature.name, 'wrong feature name'
    assert mapper_configs.feature.epsg == mapper_configs_rl.feature.epsg, 'wrong feature EPSG'
    assert mapper_configs.feature.geometry == mapper_configs_rl.feature.geometry, 'wrong feature geometry'
    assert set(mapper_configs.feature.attributes) == set(mapper_configs_rl.feature.attributes), \
        'wrong feature attributes'
    assert mapper_configs.time_start == mapper_configs_rl.time_start, 'wrong start time'
    assert mapper_configs.time_end == mapper_configs_rl.time_end, 'wrong end time'
    assert mapper_configs.collection == mapper_configs_rl.collection, 'wrong collection'
    for idx, _filter in enumerate(mapper_configs.metadata_filters):
        assert _filter.condition == mapper_configs_rl.metadata_filters[idx].condition, \
            'wrong filtering condition'
        assert _filter.entity == mapper_configs_rl.metadata_filters[idx].entity, \
            'wrong filtering entity'

@pytest.mark.parametrize(
    'collection,time_start,time_end,geom,metadata_filters',
    [(
        'sentinel2-msi-l2a',
        datetime(2022,12,1),
        datetime(2022,12,15),
        Polygon(
            [[493504.953633058525156, 5258840.576098721474409],
            [493511.206339373020455, 5258839.601945200935006],
            [493510.605988947849255, 5258835.524093257263303],
            [493504.296645800874103, 5258836.554883609525859],
            [493504.953633058525156, 5258840.576098721474409]]
        ),
        [Filter('cloud_cover_threshold','<30')],
    )]
)
def test_mapper(collection, time_start, time_end, geom, metadata_filters):
    """testing the mapper class"""
    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=32632,
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
    mapper.get_scenes()
    
    