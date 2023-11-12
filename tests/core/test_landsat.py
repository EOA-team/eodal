'''
Tests for the Landsat class.
'''

import geopandas as gpd
import numpy as np
import pytest

from datetime import datetime
from eodal.core.sensors import Landsat
from eodal.mapper.filter import Filter
from eodal.metadata.stac.client import landsat as landsat_stac
from shapely.geometry import box


def test_landsat_from_usgs():

    # query STAC for a custom region
    collection = 'landsat-c2-l2'
    bbox = box(*[7.7, 47.7, 8.0, 48.0])

    years = [1996, 2023]

    for year in years:
        time_start = datetime(year, 5, 1)
        time_end = datetime(year, 5, 30)
    
        metadata_filters = [
            Filter('eo:cloud_cover', '<', 70)
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
            band_selection=['B1', 'B2', 'B3', 'B4', 'B5', 'B6']
        )
        assert landsat.band_names == \
            ['blue', 'green', 'red', 'nir08', 'swir16'], 'wrong band names'
        assert landsat.band_aliases == \
            ['B1', 'B2', 'B3', 'B4', 'B5'], 'wrong band aliases'
        for band_name in landsat.band_names[:-1]:
            assert 0 < landsat[band_name].values.min() <= 1, 'wrong value'
            assert 0 < landsat[band_name].values.max() <= 1, 'wrong value'

        # get the cloud mask -> this should fail because we didn't
        # read the qa bands
        with pytest.raises(KeyError):
            cloud_mask = landsat.get_cloud_and_shadow_mask()

        # repeat the reading of the scene WITH the qa bands
        band_selection = ['blue', 'green', 'red', 'nir08', 'swir12']
        landsat = Landsat.from_usgs(
            in_dir=landsat_scene_item['assets'],
            vector_features=gdf,
            read_qa=True,
            read_atcor=False,
            band_selection=band_selection
        )
        assert 'qa_pixel' in landsat.band_names, 'missing quality band'

        # now the generation of a binary cloud mask should work
        cloud_mask = landsat.get_cloud_and_shadow_mask()
        assert cloud_mask.values.dtype == bool, 'expected boolean'

        water_mask = landsat.get_water_mask()
        assert water_mask.values.dtype == 'bool', 'expected boolean'
        
        # mask clouds and shadows -> check if the mask has an effect
        landsat.mask_clouds_and_shadows(inplace=True)
        assert landsat['blue'].is_masked_array, 'expected as masked array'

        # calculate the NDVI
        landsat.calc_si(si_name='NDVI', inplace=True)
        assert 'NDVI' in landsat.band_names
        assert -1 <= landsat['NDVI'].values.min() <= 1
        assert -1 <= landsat['NDVI'].values.max() <= 1
        assert np.isnan(landsat['NDVI'].nodata)

        # repeat the reading of the scene WITH the atcor bands
        band_selection = ['blue', 'green', 'red', 'nir08', 'swir12']
        landsat = Landsat.from_usgs(
            in_dir=landsat_scene_item['assets'],
            vector_features=gdf,
            read_qa=True,
            read_atcor=True,
            band_selection=band_selection
        )
        assert 'lwir' in landsat.band_names
