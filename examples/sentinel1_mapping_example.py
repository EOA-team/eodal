"""
Example script to extract a time series of Sentinel-1 mapper for a
custom area of interest (AOI).

The script shows how to use the Sentinel1Mapper class that takes over
data handling such as

    * querying of spatio-temporal metadata catalogs to identify
      available Sentinel-1 mapper
    * merging data from different Sentinel-1 tiles if required
    * re-projection of imagery from one UTM zone into another
      if required

This script works either using local data sources or by retrieving Sentinel-1
imagery from Microsoft Planetary Computer (https://planetarycomputer.microsoft.com).
To use the RTC collection (sentinel-1-rtc, radiometrically terrain corrected) you
have to specify a valid PL API key.

To use Planetary Computer make sure to set the `USE_STAC` variable to True
and specify Microsoft as STAC provider (default). If you want to use the RTC product
make sure to provide a valid Planetary Computer SDK subscription key.

.. code-block:: shell

    export USE_STAC = "True"
    export PC_SDK_SUBSCRIPTION_KEY = <your-api-key-(optional-for-RTC)>

Copyright (C) 2022 Lukas Valentin Graf

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

from datetime import date
from eodal.operational.mapping import Sentinel1Mapper
from eodal.operational.mapping import plot_feature
from pathlib import Path

#%% user-inputs

# ------------------------- Time Range ---------------------------------
date_start: date = date(2022,4,1)          # year, month, day (incl.)
date_end: date = date(2022,4,14)           # year, month, day (incl.)

# ---------------------- Area of Interest ------------------------------
aoi: Path = Path('../data/sample_polygons/lake_lucerne.gpkg')

# ---------------------- Sentinel-1 collection --------------------------
collection = 'sentinel-1-rtc'


#%% executable part
# get a new mapper instance
mapper = Sentinel1Mapper(
    date_start=date_start,
    date_end=date_end,
    feature_collection=aoi,
    collection=collection
)

# retrieve metadata of mapper found (no reading)
mapper.get_scenes()
mapper.observations
