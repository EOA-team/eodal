'''
Tests for the pystac client interface
'''

import pytest

from datetime import date

from eodal.mapper.filter import Filter
from eodal.metadata.stac import sentinel1, sentinel2
from eodal.utils.sentinel1 import _url_to_safe_name
from eodal.utils.sentinel2 import ProcessingLevels

def test_mspc_sentinel1(get_polygons):
    """Sentinel-1 GRD and RTC from MSPC"""

    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    polys = get_polygons()

    res_s1 = sentinel1(
        time_start=date_start,
        time_end=date_end,
        bounding_box=polys,
        metadata_filters=[],
        platform='s1'
    )

    assert not res_s1.empty, 'no mapper found'
    assert 'assets' in res_s1.columns, 'no assets provided'
    url = _url_to_safe_name(res_s1.iloc[0].assets['vh']['href'])
    assert 'GRDH' in url, 'GRD not found in file name'
    assert 'rtc' in res_s1.iloc[0].assets['vh']['href'], 'RTC not found in file name'

    # test GRD
    res_grd_s1 = sentinel1(
        time_start=date_start,
        time_end=date_end,
        bounding_box=polys,
        platform='s1',
        metadata_filters=[Filter('product_type','==','GRD')]
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
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)
    # select processing level
    processing_level = 'Level-2A'
    # set scene cloud cover threshold [%]
    cloud_cover_threshold = 80

    polys = get_polygons()

    metadata_filters = [
        Filter('cloudy_pixel_percentage', '<', cloud_cover_threshold),
        Filter('processing_level', '==', processing_level)
    ]

    # run stack query and make sure some items are returned
    res_s2 = sentinel2(
        time_start=date_start,
        time_end=date_end,
        bounding_box=polys,
        metadata_filters=metadata_filters,
        platform='s2'
    )
    assert not res_s2.empty, 'no results found'
    assert 'assets' in res_s2.columns, 'no assets provided'
