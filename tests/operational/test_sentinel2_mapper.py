
import pytest
import geopandas as gpd

from datetime import date
from pathlib import Path

from eodal.operational.mapping import MapperConfigs, Sentinel2Mapper
from eodal.utils.sentinel2 import ProcessingLevels
from eodal.core.raster import RasterCollection
from eodal.core.sensors import Sentinel2

@pytest.mark.parametrize(
    'date_start, date_end, processing_level',
    [(date(2016,12,1), date(2017,1,31), ProcessingLevels.L1C),
     (date(2016,12,1), date(2017,1,31), ProcessingLevels.L2A)]
)
def test_point_extraction(get_points, date_start, date_end, processing_level):
    """Extraction of points from Sentinel-2 mapper"""
    points = get_points()

    mapping_config = MapperConfigs()
    mapper = Sentinel2Mapper(
        processing_level=processing_level,
        feature_collection=points,
        date_start=date_start,
        date_end=date_end,
        mapper_configs=mapping_config
    )

    assert isinstance(mapper.feature_collection, Path), 'expected a path-like object'
    # query the DB to get all S2 mapper available for the points
    mapper.get_scenes()
    assert isinstance(mapper.feature_collection, dict), 'expected a dict-like object'
    assert len(mapper.get_feature_ids()) == 12, 'wrong number of point features'

    all_obs = mapper.get_complete_timeseries()
    assert isinstance(all_obs, dict), 'expected a dict-like object'
    assert len(all_obs) == len(mapper.get_feature_ids()), 'not all features extracted'

    for feature in all_obs:
        test_feature = all_obs[feature]
        assert isinstance(test_feature, gpd.GeoDataFrame), 'expected a GeoDataFrame'
        assert 'sensing_date' in test_feature.columns, 'sensing date is required'
        assert test_feature.sensing_date.count() == test_feature.shape[0], \
            'sensing date must not be Null'
        assert test_feature.iloc[:,test_feature.columns.str.startswith('B')].shape == \
            (test_feature.shape[0], 10), 'wrong number of spectral bands'
        assert (test_feature.iloc[:,test_feature.columns.str.startswith('B')].max() < 1).all(), \
            'expected spectral reflectance values to be smaller than one'
        assert (test_feature.iloc[:,test_feature.columns.str.startswith('B')].min() > 0).all(), \
            'expected spectral reflectance values to be larger than zero'
        if processing_level == ProcessingLevels.L1C:
            assert 'SCL' not in test_feature.columns, 'Level 1C has no scene classification layer'
        elif processing_level == ProcessingLevels.L2A:
            assert 'SCL' in test_feature.columns, 'Level 2A should have scene classification layer'

@pytest.mark.parametrize(
    'date_start, date_end, processing_level',
    [(date(2016,12,1), date(2017,1,31), ProcessingLevels.L2A),
     (date(2016,12,1), date(2017,1,31), ProcessingLevels.L1C)]
)
def test_field_parcel_extraction(get_polygons_3, date_start, date_end, processing_level):
    """Extraction of a polygon from multiple Sentinel-2 tiles"""
    polygons = get_polygons_3()

    mapping_config = MapperConfigs()
    mapper = Sentinel2Mapper(
        processing_level=processing_level,
        feature_collection=polygons,
        date_start=date_start,
        date_end=date_end,
        mapper_configs=mapping_config
    )
    assert isinstance(mapper.feature_collection, Path), 'expected a path-like object'
    # query the DB to get all S2 mapper available for the Polygon
    mapper.get_scenes()
    assert len(mapper.observations) == 1, 'expected a single feature'
    feature_id = mapper.get_feature_ids()[0]
    obs = mapper.observations[feature_id]
    # the polygon covers three different S2 tiles
    assert set(obs.tile_id.unique()) == {'T32TLT', 'T31TGN', 'T32TLS'}, \
        'expected three different tiles here'
    # the target CRS should be 32632 (UTM Zone 32N) because the majority of the
    # mapper is in that projection
    assert (obs.target_crs == 32632).all(), 'wrong target CRS'
    if processing_level == ProcessingLevels.L1C:
        assert set(obs.sensing_date.unique()) == {date(2016,12,1), date(2017,1,3)}, \
            'expected two different dates'
        assert obs.is_split.all(), 'all mapper must be flagged as "split"'

    # get single observation
    res = mapper.get_observation(
        feature_id=feature_id,
        # sensing_date=date(2016,12,10)
        sensing_date=date(2017,1,17)
    )
    assert isinstance(res, Sentinel2), 'expected a raster collection for Sentinel-2 data'
    assert res.is_bandstack(), 'all bands must have the same extent, CRS and pixel size'
    if processing_level == ProcessingLevels.L1C:
        assert 'SCL' not in res.band_names, 'L1C has no SCL'
    elif processing_level == ProcessingLevels.L2A:
        assert 'SCL' in res.band_names, 'expected SCL'

    # get all observations in the time period queried
    res = mapper.get_complete_timeseries(feature_selection=[feature_id])
    assert isinstance(res, dict), 'expected a dict here'
    assert len(res) == 1, 'expected a single feature, only'
    assert isinstance(res[feature_id], list), 'expected a list here'
    assert len(res[feature_id]) == len(mapper.observations[feature_id].sensing_date.unique()), \
        'expected a single dataset per sensing date'
    scenes = res[feature_id]
    assert all([isinstance(x, Sentinel2) for x in scenes]), \
        'expected a list of Sentinel-2 objects'
    