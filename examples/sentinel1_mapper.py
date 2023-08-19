"""
Script to extract a collection of Sentinel-1 RTC scenes for a
custom area of interest (AOI).

The script should run as is on Microsoft Planetary Computer Hub
(https://planetarycomputer.microsoft.com/compute).

When using locally, make sure you have a valid MSPC subscription key
(see also:
https://planetarycomputer.microsoft.com/docs/concepts/sas/#when-an-account-is-needed)

The key must be made available to EOdal using the PC_SDK_SUBSCRIPTION_KEY

Copyright (C) 2022/23 Lukas Valentin Graf

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
from eodal.config import get_settings
from eodal.core.sensors import Sentinel1
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs
from shapely.geometry import box

Settings = get_settings()
Settings.USE_STAC = True

if __name__ == '__main__':

    collection = 'sentinel1-grd'
    # define time period
    time_start = datetime(2020, 7, 1)
    time_end = datetime(2020, 7, 15)

    # define input geometry
    bbox = [9.0924, 47.5992, 9.2190, 47.7295]
    geom = box(*bbox)
    metadata_filters = [Filter('product_type', '==', 'RTC')]

    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=4326,
        attributes={'id': 1}
    )
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()

    mapper.metadata

    scene_kwargs = {
        'scene_constructor': Sentinel1.from_safe,
        'scene_constructor_kwargs': {}
    }
    mapper.load_scenes(scene_kwargs=scene_kwargs)
    f = mapper.data.plot(band_selection=['VH'], figsize=(20, 10))
