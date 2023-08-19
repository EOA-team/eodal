"""
Script to extract a collection of Landsat scenes for a
custom area of interest (AOI).

The script shows how to use the EOdal Mapper class that takes over
data handling such as

* querying of spatio-temporal metadata catalogs to identify
available Landsat scenes
* merging data from different tiles if required
* re-projection of imagery from one UTM zone into another if required
* removal of black-filled (i.e., no-data) scenes

This script works by retrieving Landsat Collection-2 scenes from
Microsoft Planetary Computer (https://planetarycomputer.microsoft.com).
This requires no authentication required. Alternatively, the same code
can be used to read data from a local EOdal Sentinel archive or a different
STAC provider.

Copyright (C) 2023 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from datetime import datetime
from pathlib import Path
from shapely.geometry import box

from eodal.config import get_settings
from eodal.core.sensors import Landsat
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs

Settings = get_settings()
# we use STAC, i.e., Microsoft Planetary Computer
Settings.USE_STAC = True


def prepocess_landsat_scene(
        ds: Landsat
) -> Landsat:
    """
    Mask clouds and cloud shadows in a Landsat scene based
    on the 'qa_pixel' band.

    NOTE:
        Depending on your needs, the pre-processing function can be
        fully customized using the full power of EOdal and its
        interfacing libraries!

    :param ds:
        Landsat scene before cloud mask applied.
    :return:
        Landsat scene with clouds and cloud shadows masked.
    """
    ds.mask_clouds_and_shadows(inplace=True)
    return ds


if __name__ == "__main__":

    import os
    cwd = Path(__file__).parents[1]
    os.chdir(cwd)

    # user-inputs
    # -------------------------- Collection -------------------------------
    collection = 'landsat-c2-l2'

    # ---------------------- Spatial Feature  ------------------------------
    bbox = box(*[7.5, 47.5, 8.0, 48.0])  # can be also shp, gpkg, etc.
    feature = Feature(
        name='landsat-test',
        geometry=bbox,
        epsg=4326,
        attributes={})

    # ------------------------- Time Range ---------------------------------
    time_start = datetime(2023, 5, 1)
    time_end = datetime(2023, 5, 31)

    # ------------------------- Metadata Filters ---------------------------
    metadata_filters = [
        Filter('eo:cloud_cover', '<', 70),
        Filter('landsat:wrs_row', '==', '027')
    ]

    # set up the Mapper configuration
    mapper_configs = MapperConfigs(
        metadata_filters=metadata_filters,
        collection=collection,
        feature=feature,
        time_start=time_start,
        time_end=time_end)
    # get a new mapper instance
    mapper = Mapper(mapper_configs)

    # query the scenes available (no I/O of scenes, this only fetches metadata)
    mapper.query_scenes()
    # the metadata is stored as a GeoDataFrame
    mapper.metadata

    # we tell EOdal how to load the Landsat scenes using `Landsat.from_usgs`
    # and pass on some kwargs, e.g., the selection of bands we want to read.
    # in addition, we tell EOdal to mask out clouds and shadows and the fly
    # while reading the data using the qa_pixel band (therefore, we set the
    # `read_qa` flag to True.
    scene_kwargs = {
        'scene_constructor': Landsat.from_usgs,
        'scene_constructor_kwargs': {
            'band_selection': ["blue", "green", "red", "nir08"],
            'read_qa': True},
        'scene_modifier': prepocess_landsat_scene,
        'scene_modifier_kwargs': {}}

    # now we load the scenes
    mapper.load_scenes(scene_kwargs=scene_kwargs)
    # the scenes are loaded into a EOdal SceneCollection object
    mapper.data

    # test scene for cloud masking
    scene = mapper.data[mapper.data.timestamps[-1]]

    # the scenes can be plotted
    f_scenes = mapper.data.plot(['red', 'green', 'blue'], figsize=(15,5))

    # make the SceneCollection obtained persistent so that we do not have to re-run
    # the STAC query all the time we use the data.
    fpath = Path('data/sample_mapper_data.pkl')
    with open(fpath, 'wb+') as dst:
        dst.write(mapper.data.to_pickle())
