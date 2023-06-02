'''
Tests for the Landsat class.
'''

import geopandas as gpd
import pytest

from datetime import datetime
from eodal.core.sensors import Landsat
from eodal.mapper.filter import Filter
from eodal.metadata.stac.client import landsat as landsat_stac
from shapely.geometry import box


def test_landsat_from_usgs():

    # query STAC for a custom region
    collection = 'landsat_mapper-c2-l2'
    bbox = box(*[7.0, 47.0, 8.0, 48.0])

    years = [1995, 2023]

    for year in years:
        time_start = datetime(year, 5, 1)
        time_end = datetime(year, 5, 30)
    
        metadata_filters = [
            Filter('eo:cloud_cover', '<', 70),
            Filter('landsat_mapper:wrs_row', '==', '028')
        ]

        landsat_items = landsat_stac(
            metadata_filters=metadata_filters,
            collection=collection,
            bounding_box=bbox,
            time_start=time_start,
            time_end=time_end)
    
        # read only a part of the test scene
        landsat_scene_item = landsat_items.iloc[0]
        gdf = gpd.GeoSeries([bbox], crs=4326)
        landsat = Landsat.from_usgs(
            in_dir=landsat_scene_item['assets'],
            vector_features=gdf,
            read_qa=False,
            read_atcor=False,
            band_selection=['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'qa']
        )
        assert landsat.band_names == \
            ['coastal', 'blue', 'green', 'red', 'nir08', 'swir16', 'qa'], 'wrong band names'
        assert landsat.band_aliases == \
            ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'qa'], 'wrong band aliases'
        for band_name in landsat.band_names[:-1]:
            assert 0 < landsat[band_name].values.min() <= 1, 'wrong value'
            assert 0 < landsat[band_name].values.max() <= 1, 'wrong value'
