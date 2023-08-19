"""
Script to get the least cloudy Sentinel-2 scene by month
and area of interest. The script is based on the EOdal Mapper.

The scene is saved to GeoTiff alongside its granule metadata xml.

@author: Lukas Valentinb Graf
"""

import geopandas as gpd
import planetary_computer
import urllib

from datetime import datetime
from eodal.config import get_settings
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.core.sensors.sentinel2 import Sentinel2
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

from pathlib import Path
from typing import List


Settings = get_settings()
# set to False to use a local data archove
Settings.USE_STAC = True


if __name__ == '__main__':

    # -------------------------- Paths -------------------------------------
    # define the output directory
    out_dir = Path('./data')

    # user-inputs
    # -------------------------- Collection -------------------------------
    collection: str = 'sentinel2-msi'

    # ------------------------- Time Range ---------------------------------
    time_start: datetime = datetime(2022, 6, 1)  		# year, month, day (incl.)
    time_end: datetime = datetime(2022, 6, 30)   		# year, month, day (incl.)

    # ---------------------- Spatial Feature  ------------------------------
    geom = \
        'https://raw.githubusercontent.com/neffjulian/remote_sensing/main/images/coordinates/zhr_coordinates.geojson'  # noqa: E501

    # ------------------------- Metadata Filters ---------------------------
    metadata_filters: List[Filter] = [
        Filter('cloudy_pixel_percentage', '<=', 25),
        Filter('processing_level', '==', 'Level-2A')]

    # query the scenes available (no I/O of scenes, this only fetches metadata)
    feature = Feature.from_geoseries(gpd.read_file(geom).geometry)
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters)
    # to enhance reproducibility and provide proper documentation, the MapperConfigs
    # can be saved as yaml (and also then be loaded again from yaml)
    mapper_configs.to_yaml(out_dir.joinpath('sample_mapper_call.yaml'))

    # now, a new Mapper instance is created
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()
    # the metadata is loaded into a GeoPandas GeoDataFrame
    mapper.metadata

    # get the least cloudy scene
    mapper.metadata = mapper.metadata[
        mapper.metadata.cloudy_pixel_percentage ==
        mapper.metadata.cloudy_pixel_percentage.min()].copy()

    # load the least cloudy scene available from STAC
    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {
            'band_selection': ["B02", "B03", "B04", "B05", "B8A"]}}

    mapper.load_scenes(scene_kwargs=scene_kwargs)
    # the data loaded into `mapper.data` as a EOdal SceneCollection
    # it should now contain only a single scene
    scene = mapper.data[mapper.data.timestamps[0]]

    # save the scene to disk
    # we distinguish the 10 and 20m bands by the suffixes _10m and _20m
    scene_10m = RasterCollection()
    for band in ['blue', 'green', 'red']:
        scene_10m.add_band(scene[band])
    scene_10m.to_rasterio(out_dir.joinpath('scene_10m.tif'))

    scene_20m = RasterCollection()
    for band in ['red_edge_1', 'nir_2']:
        scene_20m.add_band(scene[band])
    scene_20m.to_rasterio(out_dir.joinpath('scene_20m.tif'))

    # save metadata xml to disk
    href_xml = mapper.metadata.assets.iloc[0]['granule-metadata']['href']
    response = urllib.request.urlopen(
        planetary_computer.sign_url(href_xml)).read()
    fpath_xml = out_dir.joinpath(href_xml.split('/')[-1])
    with open(fpath_xml, 'wb') as dst:
        dst.write(response)

    # plot scene
    fig = scene_10m.plot_multiple_bands(band_selection=['blue', 'green', 'red'])
    fig.savefig(out_dir.joinpath('scene_10m.png'), dpi=300)
