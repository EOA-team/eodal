"""
REST-API based downloading of Sentinel-1 datasets from CREODIAS.

Make sure to have a valid CREODIAS account and provide your username and password
as environmental variables:

On a Linux system you can specify your credentials in the current Python environment
by:

.. code-block:: shell

    export CREODIAS_USER = "<your-user-name>"
    export CREODIAS_PASSWORD= "<your-password>"

Copyright (C) 2022 Gregor Perich and Lukas Valentin Graf

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

from eodal.config import get_settings

Settings = get_settings()
logger = Settings.logger

CREODIAS_FINDER_URL = (
    "https://finder.creodias.eu/resto/api/collections/Sentinel1/search.json?"
)


def query_creodias(
    start_date: date,
    end_date: date,
    max_records: int,
    bounding_box: Polygon,
    product_type: Optional[str] = "GRD",
    sensor_mode: Optional[str] = "IW",
) -> pd.DataFrame:
    """
    queries the CREODIAS Finder API to obtain available Sentinel-1
    datasets for a given geographic region, date range, product type,
    and sensor mode.

    NO AUTHENTICATION is required for running this query.

    :param start_date:
        start date of the queried time period (inclusive)
    :param end_date:
        end date of the queried time period (inclusive)
    :param max_records:
        maximum number of items returned. NOTE that
        CREODIAS might limit this number!
    :param bounding_box:
        polygon in geographic coordinates (WGS84) denoting
        the queried region
    :param product_type:
        Sentinel-1 product type. GRD (Ground Range Detected) by default.
    :param sensor_mode:
        Sentinel-1 sensor mode. IW (Interferometric Wide Swath) by default.
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

    # construct the REST query
    query = CREODIAS_FINDER_URL + f"maxRecords={max_records}&"
    query += f"startDate={start_date_str}T00%3A00%3A00Z&"
    query += f"completionDate={end_date_str}T23%3A59%3A59Z&"
    query += f"productType={product_type}&"
    query += f"sensorMode={sensor_mode}&"
    query += f"geometry=Polygon(({coord_str}))&"
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
        raise Exception(f"CREODIAS query returned empty set")

    # get *.SAFE dataset names
    datasets["dataset_name"] = datasets.properties.apply(
        lambda x: x["productIdentifier"].split("/")[-1]
    )

    return datasets
