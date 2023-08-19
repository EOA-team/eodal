"""
Script to get NDVI from Sentinel-2 for a specific area of interest
(e.g., a field parcel) for a pre-defined time period.

@author: Lukas Valentin Graf
"""

import geopandas as gpd

from datetime import datetime
from eodal.config import get_settings
from eodal.core.sensors.sentinel2 import Sentinel2
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

from pathlib import Path
from typing import List


Settings = get_settings()
# set to False to use a local data archive
Settings.USE_STAC = True


def get_ndvi(
    mapper: Mapper,
    output_dir: Path
) -> None:
    """
    Fetch Sentinel-2 scenes, calculate the NDVI and
    save the NDVI as geoTiff files.

    :param mapper:
        eodal Mapper instance
    :param output_dir:
        directory where to save the GeoTiff files to
    """
    mapper.query_scenes()

    # load the scenes available from STAC
    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {
            'band_selection': ["B04", "B08"]}}
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    # calculate the NDVI
    for scene_timestamp, scene in mapper.data:
        scene.calc_si('NDVI', inplace=True)
        # save NDVI as GeoTiff
        fpath_ndvi = output_dir.joinpath(
            f'{scene_timestamp}_ndvi.tif'
        )
        scene['ndvi'].to_rasterio(fpath_ndvi)


if __name__ == '__main__':

    import os
    cwd = Path(__file__).parents[1]
    os.chdir(cwd)

    # -------------------------- Paths -------------------------------------
    # define the output directory where to save the NDVI GeoTiff files
    output_dir = cwd.joinpath('data')

    # user-inputs
    # -------------------------- Collection -------------------------------
    collection: str = 'sentinel2-msi'

    # ------------------------- Time Range ---------------------------------
    time_start: datetime = datetime(2022, 6, 1)  		# year, month, day (incl.)
    time_end: datetime = datetime(2022, 6, 30)   		# year, month, day (incl.)

    # ----------------------- Cloudy Pixel Percentage ----------------------
    cloudy_pixel_percentage: int = 25  # percent (scene-wide)

    # ---------------------- Spatial Feature  ------------------------------
    geom = cwd.joinpath(
        'data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp')

    # ------------------------- Metadata Filters ---------------------------
    metadata_filters: List[Filter] = [
        Filter('cloudy_pixel_percentage', '<=', cloudy_pixel_percentage),
        Filter('processing_level', '==', 'Level-2A')]

    # query the scenes available (no I/O of scenes, this only fetches metadata)
    feature = Feature.from_geoseries(gpd.read_file(geom).geometry)
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters)

    # now, a new Mapper instance is created
    mapper = Mapper(mapper_configs)

    get_ndvi(mapper, output_dir)
