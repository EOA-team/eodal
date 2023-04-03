"""
REST-API based downloading of Sentinel-2 datasets from CREODIAS.

Make sure to have a valid CREODIAS account and provide your username and password
as environmental variables:

On a Linux system you can specify your credentials in the current Python environment
by:

.. code-block:: shell

    export CREODIAS_USER = "<your-user-name>"
    export CREODIAS_PASSWORD= "<your-password>"

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

import pandas as pd
import requests

from datetime import date
from shapely.geometry import Polygon
from typing import Optional

from eodal.utils.constants.sentinel2 import ProcessingLevels
from eodal.utils.exceptions import DataNotFoundError

CREODIAS_FINDER_URL = (
    "https://finder.creodias.eu/resto/api/collections/Sentinel2/search.json?"
)


def query_creodias(
    start_date: date,
    end_date: date,
    max_records: int,
    processing_level: ProcessingLevels,
    bounding_box: Polygon,
    cloud_cover_threshold: Optional[int] = 100,
) -> pd.DataFrame:
    """
    queries the CREODIAS Finder API to obtain available
    datasets for a given geographic region, date range and
    Sentinel-2 processing level (L1C or L2A).

    NO AUTHENTICATION is required for running this query.

    :param start_date:
        start date of the queried time period (inclusive)
    :param end_date:
        end date of the queried time period (inclusive)
    :param max_records:
        maximum number of items returned. NOTE that
        CREODIAS might limit this number!
    :param processing_level:
        queried Sentinel-2 processing level
    :param bounding_box:
        polygon in geographic coordinates (WGS84) denoting
        the queried region
    :param cloud_cover_threshold:
        cloudy pixel percentage threshold (0-100%) for filtering
        mapper too cloudy for processing. All mapper with a cloud
        cover lower than the threshold specified will be downloaded.
        Per default all mapper are downloaded.
    :returns:
        results of the CREODIAS query (no downloaded data!)
        as pandas DataFrame
    """

    # convert dates to strings in the required format
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # convert polygon to required format
    coords = bounding_box.exterior.coords.xy
    coord_str = ""
    n_points = len(coords[0])
    for n_point in range(n_points):
        x = coords[0][n_point]
        y = coords[1][n_point]
        coord_str += f"{x}+{y}%2C"

    # get rid of the last %2C
    coord_str = coord_str[:-3]
    # adopt the processing level
    processing_level_creodias = processing_level.value.replace("-", "").upper()
    # construct the REST query
    query = CREODIAS_FINDER_URL + f"maxRecords={max_records}&"
    query += f"startDate={start_date_str}T00%3A00%3A00Z&completionDate={end_date_str}T23%3A59%3A59Z&"
    query += f"cloudCover=%5B0%2C{cloud_cover_threshold}%5D&"
    query += f"processingLevel={processing_level_creodias}&"
    query += f"geometry=POLYGON(({coord_str}))&"
    query += "sortParam=startDate&sortOrder=descending&status=all&dataset=ESA-DATASET"

    # GET to CREODIAS Finder API
    res = requests.get(query)
    res.raise_for_status()
    res_json = res.json()

    # extract features (=available datasets)
    features = res_json["features"]
    datasets = pd.DataFrame(features)

    # make sure datasets is not empty otherwise return
    if datasets.empty:
        raise DataNotFoundError(f"CREODIAS query returned empty set")

    # get *.SAFE dataset names
    datasets["dataset_name"] = datasets.properties.apply(
        lambda x: x["productIdentifier"].split("/")[-1]
    )

    return datasets
