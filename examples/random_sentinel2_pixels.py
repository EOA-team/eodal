'''
Created on Oct 1, 2022

@author: graflu
'''

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd

from datetime import date
from pathlib import Path
from typing import Optional

from eodal.operational.mapping import MapperConfigs, Sentinel2Mapper
from eodal.utils.constants import ProcessingLevels

def assign_pixel_ids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assigns unique pixel IDs based on the pixel geometries

    :param gdf:
        GeoDataFrame with point geometries (pixels)
    :returns:
        the input GeoDataFrame with a new column containing unique
        pixel IDs
    """
    # we need the well-known-binary representation of the geometries
    # to allow for fast assignment of pixel IDs (pandas cannot handle
    # the actual geometries)
    gdf['wkb'] = gdf.geometry.apply(lambda x: x.wkb)
    unique_geoms = list(gdf.wkb.unique())
    pixel_ids = [x for x in range(len(unique_geoms))]
    pixel_id_mapper = dict(zip(unique_geoms, pixel_ids))
    gdf['pixel_id'] = gdf.wkb.map(pixel_id_mapper)
    return gdf

def random_choice(pixel_series: gpd.GeoSeries, n: Optional[int] = 5) -> gpd.GeoSeries:
    """
    Selects `n` observations from a pixel time series (all bands)

    :param pixel_series:
        pixel time series
    :param n:
        number of observations to sample from the series
    :returns:
        randomly selected observations
    """
    # get sensing dates available
    dates = list(pixel_series.sensing_date.unique)
    n_dates = len(dates)
    # update (lower) n if required
    if n_dates < n:
        n = n_dates
    # TODO select n dates and return the corresponding pixel values
    return

def get_pixels(date_start: date, date_end: date, scene_cloud_cover_threshold: int,
               aois: gpd.GeoDataFrame | Path, **kwargs):
    """
    Random selection of pixel observations from time series within one or more areas
    of interest (AOIS, aka features).

    :param date_start:
        start date for extracting Sentinel-2 data (inclusive)
    :param date_end:
        end date for extracting Sentinel-2 data (inclusive)
    :param scene_cloud_cover_threshold:
        scene-wide cloud cover threshold in percent [0-100]. Scenes with a cloud-cover
        higher than the threshold are not considered
    :param aois:
        areas of interest (1 to N) for which to extract random pixel observations
    """
    # setup Sentinel-2 mapper to get the relevant mapper
    mapper_configs = MapperConfigs(
        spatial_resolution=10.,
        resampling_method=cv2.INTER_NEAREST_EXACT,
        band_names=['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B11', 'B12']
    )

    # get a new mapper instance
    mapper = Sentinel2Mapper(
        date_start=date_start,
        date_end=date_end,
        processing_level=ProcessingLevels.L2A,
        cloud_cover_threshold=scene_cloud_cover_threshold,
        mapper_configs=mapper_configs,
        feature_collection=aois
    )
    # query the available mapper (spatio-temporal query in the metadata catalog)
    mapper.get_scenes()
    # extract the actual S2 data
    s2_data = mapper.get_complete_timeseries()

    # extraction is based on features (1 to N geometries)
    features = mapper.feature_collection['features']

    # loop over features and extract scene data
    for idx, feature in enumerate(features):
        feature_id = mapper.get_feature_ids()[idx]
        # mapper of the actual feature
        feature_scenes = s2_data[feature_id]
        # loop over mapper, drop non-cloudfree observations and save spectral values to GeoDataFrame
        feature_refl_list = []
        for feature_scene in feature_scenes:
            # drop all observations but SCL classes 4 and 5
            feature_scene.mask_clouds_and_shadows(inplace=True)
            # save spectral values as GeoDataFrame
            refl_df = feature_scene.to_dataframe()
            # drop nans (results from the masking of clouds)
            refl_df.drop_nan(inplace=True)
            # save the sensing date
            refl_df['sensing_date'] = pd.to_datetime(feature_scene.scene_properties.sensing_date)
            feature_refl_list.append(refl_df)
        # create a single data frame per feature
        feature_refl_df = pd.concat(feature_refl_list)
        feature_refl_df.sort_values(by='sensing_date', inplace=True)
        # assign pixel ids based on the coordinates so that sampling per pixel time series is possible
        feature_refl_df_pid = assign_pixel_ids(gdf=feature_refl_df)
        # select 5 observations per pixel (or less if there are not enough) by random choice
        feature_refl_grouped = feature_refl_df_pid.groupby(by='pixel_id')
        # apply random choice on each pixel


if __name__ == '__main__':

    date_start = date(2022,3,1)
    date_end = date(2022,3,31)
    aois = Path('../data/sample_polygons/BY_AOI_2019_MNI_EPSG32632.shp')
    scene_cloud_cover_threshold = 50

    get_pixels(
        date_start=date_start,
        date_end=date_end,
        scene_cloud_cover_threshold=scene_cloud_cover_threshold,
        aois=aois
    )  
            