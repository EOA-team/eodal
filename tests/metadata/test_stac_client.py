'''
Tests for the pystac client interface
'''

import pytest

from datetime import date

from eodal.config import get_settings, STAC_Providers
from eodal.metadata.stac import sentinel1_rtc, sentinel2
from eodal.utils.sentinel2 import ProcessingLevels

def test_mspc_sentinel1(get_polygons):
    """Sentinel-1 RTC from MSPC"""

    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    polys = get_polygons()

    res_s1 = sentinel1_rtc(
        date_start=date_start,
        date_end=date_end,
        vector_features=polys
    )

    assert not res_s1.empty, 'no scenes found'
    assert 'assets' in res_s1.columns, 'no assets provided'

def test_mspc_sentinel2(get_polygons):
    """Sentinel-2 L2A from MSPC"""

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)
    # select processing level
    processing_level = ProcessingLevels.L2A
    # set scene cloud cover threshold [%]
    cloud_cover_threshold = 80

    polys = get_polygons()

    # run stack query and make sure some items are returned
    res_s2 = sentinel2(
        date_start=date_start,
        date_end=date_end,
        processing_level=processing_level,
        cloud_cover_threshold=cloud_cover_threshold,
        vector_features=polys,
    )
    assert not res_s2.empty, 'no results found'
    assert 'assets' in res_s2.columns, 'no assets provided'

# def test_aws_sentinel2(get_polygons):
#     """Sentinel-2 L2A from AWS"""
#
#     Settings = get_settings()
#
#     # define time period
#     date_start = date(2022, 5, 1)
#     date_end = date(2022, 5, 31)
#     # select processing level
#     processing_level = ProcessingLevels.L2A
#     # set scene cloud cover threshold [%]
#     cloud_cover_threshold = 80
#
#     polys = get_polygons()
#
#     # run stack query and make sure some items are returned
#     res_s2 = sentinel2(
#         date_start=date_start,
#         date_end=date_end,
#         processing_level=processing_level,
#         cloud_cover_threshold=cloud_cover_threshold,
#         vector_features=polys,
#     )
#     assert res_s2.empty, 'no results found'
#     assert 'assets' in res_s2.columns, 'no assets provided'