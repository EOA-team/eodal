'''
Tests for the pystac client interface
'''

import pytest
import geopandas as gpd

from datetime import datetime
from shapely.geometry import box

from eodal.mapper.filter import Filter
from eodal.metadata.stac import sentinel1, sentinel2
from eodal.utils.sentinel1 import _url_to_safe_name
from eodal.utils.sentinel2 import ProcessingLevels


def test_mspc_sentinel1(get_polygons):
    """Sentinel-1 GRD and RTC from MSPC"""

    time_start = datetime(2022, 5, 1)
    time_end = datetime(2022, 5, 31)

    polys = gpd.read_file(get_polygons())
    bbox = box(*polys.to_crs(epsg=4326).total_bounds)

    # test RTC product
    metadata_filters = [Filter('product_type', '==', 'RTC')]
    res_s1 = sentinel1(
        metadata_filters=metadata_filters,
            collection='sentinel1-rtc',
            bounding_box=bbox,
            time_start=time_start,
            time_end=time_end
    )

    assert not res_s1.empty, 'no mapper found'
    assert 'assets' in res_s1.columns, 'no assets provided'
    url = _url_to_safe_name(res_s1.iloc[0].assets['vh']['href'])
    assert 'GRDH' in url, 'GRD not found in file name'
    assert 'rtc' in res_s1.iloc[0].assets['vh']['href'], 'RTC not found in file name'

    # test GRD
    metadata_filters = [Filter('product_type', '==', 'GRD')]
    res_grd_s1 = sentinel1(
        metadata_filters=metadata_filters,
            collection='sentinel1-grd',
            bounding_box=bbox,
            time_start=time_start,
            time_end=time_end
    )

    assert not res_grd_s1.empty, 'no mapper found'
    assert 'assets' in res_grd_s1.columns, 'no assets provided'
    url = _url_to_safe_name(res_grd_s1.iloc[0].assets['vh']['href'])
    assert 'GRDH' in url, 'GRD not found in file name'
    assert 'rtc' not in res_grd_s1.iloc[0].assets['vh']['href'], \
        'RTC substring found in GRD-only dataset'


def test_mspc_sentinel2(get_polygons):
    """Sentinel-2 L2A from MSPC"""

    # define time period
    time_start = datetime(2022, 5, 1)
    time_end = datetime(2022, 5, 31)
    # set scene cloud cover threshold [%]
    cloud_cover_threshold = 80

    polys = gpd.read_file(get_polygons())
    bbox = box(*polys.to_crs(epsg=4326).total_bounds)

    metadata_filters = [
        Filter('cloudy_pixel_percentage', '<', cloud_cover_threshold),
        Filter('processing_level', '==', 'Level-2A')
    ]

    # run stack query and make sure some items are returned
    res_s2 = sentinel2(
        metadata_filters=metadata_filters,
            collection='sentinel2-msi',
            bounding_box=bbox,
            time_start=time_start,
            time_end=time_end
    )
        
    assert not res_s2.empty, 'no results found'
    assert 'assets' in res_s2.columns, 'no assets provided'
