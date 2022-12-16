"""
This module is a very basic approach to query the Sentinel Copernicus
archive using the Sentinelsat package as API client.
Before executing, make sure to have DHUS_USER and DHUS_PASSWORD
stored as environmental variables (and to have access to the API hub).
See also the Sentinelsat docs for more information:
https://sentinelsat.readthedocs.io/en/stable/index.html

On a Linux system you can specify your credentials in the current Python environment
by:

.. code-block:: shell

    export DHUS_USER = "<your-user-name>"
    export DHUS_PASSWORD= "<your-password>"

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
from __future__ import annotations

import os
from pathlib import Path
from enum import Enum
from typing import Optional
from datetime import date
import pandas as pd
import geopandas as gpd
from sentinelsat import SentinelAPI

from eodal.config import get_settings

Settings = get_settings()
logger = Settings.logger

# take credentials from the environmental variables and authenticate
URL = "https://apihub.copernicus.eu/apihub"
DHUS_USER = os.getenv("DHUS_USER", "")
DHUS_PASSWORD = os.getenv("DHUS_PASSWORD", "")
api = SentinelAPI(DHUS_USER, DHUS_PASSWORD, URL)


class Platforms(Enum):
    Sentinel1 = "Sentinel-1"
    Sentinel2 = "Sentinel-2"
    Sentinel3 = "Sentinel-3"


def query_from_copernicus(
    footprint_file: Path,
    date_start: date,
    date_end: date,
    platform: Platforms,
    cloud_cover_threshold: Optional[float] = 80.0,
    **kwargs,
) -> pd.DataFrame:
    """
    This method can be used to query Sentinel (1,2,3) data
    from Copernicus Scientific Data Hub (DHUS) using the user
    provided credentials for calling the product search API.

    NOTE: Since Copernicus changed its archive policy to a
    rolling-archive, older data might not be maintained in the
    SciHub archive (i.e., it is not "online") and has to be
    requested from the long-term archive (LTA). Alternatively,
    downloading from a national data access point or DIAS is
    recommended if the data requested is in the LTA.

    :param footprint_file:
        filepath to any vector file containing the geometry for which
        to search and optionally download Sentinel data
    :param date_start:
        start date of the search period
    :param date_end:
        end date of the search period
    :param platform:
        name of the Sentinel platform (1,2,3) to download
    :param cloud_cover_threshold:
        cloud cover percentage threshold (0-100 percent). Scenes with a
        cloud cover percentage higher than the threshold are discarded.
        The default is 80 percent.
    :param download_data:
        boolean flag indicating if found dataset shall be donwloaded
        or not. The default is True (i.e, download data).
    :param kwargs:
        additional keyword arguments to use to filter the dataframe
        containing the found products. It only works for filtering that
        equals one property to an threshold or given value. For more
        advanced filtering apply the custom filtering logic in the
        calling script.
    :return products:
        data frame with the found datasets (products).
    """

    # read file with footprint geometry and convert it to WKT
    try:
        gdf = gpd.read_file(footprint_file)
    except Exception as e:
        logger.error(f"Could not read data from {footprint_file}")
        return pd.DataFrame()

    if gdf.shape[0] > 1:
        logger.warn(
            "Got more than one footprint feature; take the first and ignore the rest"
        )

    # check spatial reference system
    src_epsg = gdf.crs.to_epsg()
    if src_epsg != 4326:
        gdf = gdf.to_crs(4326)

    footprint = gdf.geometry.iloc[0].wkt

    products = api.query(
        footprint, date=(date_start, date_end), platformname=platform.value
    )

    # convert to pandas dataframe
    products_df = api.to_dataframe(products)

    # filter by cloud cover
    product_cc_filtered = products_df[
        products_df.cloudcoverpercentage <= cloud_cover_threshold
    ].copy()

    # filter by further optional arguments if any
    if len(kwargs) > 0:
        try:
            custom_filtered = product_cc_filtered.loc[
                (product_cc_filtered[list(kwargs)] == pd.Series(kwargs)).all(axis=1)
            ].copy()
        except Exception as e:
            logger.error(f"Could not apply filtering logic {e}. Return unfiltered df")
            return product_cc_filtered
        return custom_filtered
    else:
        return product_cc_filtered


def download_data(df: pd.DataFrame, download_dir: Path) -> None:
    """
    downloads Sentinel products from Copernicus DHUS
    using the download API client implemented in Sentinelsat.

    :param df:
        dataframe containing products URIs and links
        returned from calling Sentinelsat's API client
    :param download_dir:
        directory where to download the data to
    """
    try:
        api.download_all(df.index, directory_path=download_dir)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return
