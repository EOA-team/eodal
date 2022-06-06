'''
REST-API based downloading of Copernicus datasets from CREODIAS.

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
'''

import os
import requests
import pandas as pd

from pathlib import Path
from datetime import date
from shapely.geometry import Polygon
from typing import Optional
from typing import Union

from eodal.config import get_settings
from eodal.utils.constants.sentinel2 import ProcessingLevels
from eodal.utils.exceptions import DataNotFoundError


Settings = get_settings()
logger = Settings.logger

CREODIAS_FINDER_URL = 'https://finder.creodias.eu/resto/api/collections/Sentinel2/search.json?'
CHUNK_SIZE = 2096


def query_creodias(
        start_date: date,
        end_date: date,
        max_records: int,
        processing_level: ProcessingLevels,
        bounding_box: Polygon,
        cloud_cover_threshold: Optional[int]=100
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
        scenes too cloudy for processing. All scenes with a cloud
        cover lower than the threshold specified will be downloaded.
        Per default all scenes are downloaded.
    :return:
        results of the CREODIAS query (no downloaded data!)
        as pandas DataFrame
    """

    # convert dates to strings in the required format
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # convert polygon to required format
    coords = bounding_box.exterior.coords.xy
    coord_str = ''
    n_points = len(coords[0])
    for n_point in range(n_points):
        x = coords[0][n_point]
        y = coords[1][n_point]
        coord_str += f'{x}+{y}%2C'

    # get rid of the last %2C
    coord_str = coord_str[:-3]
    # construct the REST query
    query = CREODIAS_FINDER_URL + f'maxRecords={max_records}&'
    query += f'startDate={start_date_str}T00%3A00%3A00Z&completionDate={end_date_str}T23%3A59%3A59Z&'
    query += f'cloudCover=%5B0%2C{cloud_cover_threshold}%5D&'
    query += f'processingLevel={processing_level.value}&'
    query += f'geometry=Polygon(({coord_str}))&'
    query += 'sortParam=startDate&sortOrder=descending&status=all&dataset=ESA-DATASET'

    # GET to CREODIAS Finder API
    res = requests.get(query)
    res.raise_for_status()
    res_json = res.json()

    # extract features (=available datasets)
    features = res_json['features']
    datasets = pd.DataFrame(features)

    # make sure datasets is not empty otherwise return
    if datasets.empty:
        raise DataNotFoundError(f'CREODIAS query returned empty set')

    # get *.SAFE dataset names
    datasets['dataset_name'] = datasets.properties.apply(
        lambda x: x['productIdentifier'].split('/')[-1]
    )

    return datasets


def get_keycloak() -> str:
    """
    Returns the CREODIAS keycloak token for a valid
    (i.e., registered) CREODIAS user. Takes the username
    and password from either config/settings.py, a .env
    file or environment variables.

    The token is required for downloading data from
    CREODIAS.

    Function taken from:
    https://creodias.eu/-/how-to-generate-keycloak-token-using-web-browser-console-
    (2021-09-23)
    """

    data = {
        "client_id": "CLOUDFERRO_PUBLIC",
        "username": Settings.CREODIAS_USER,
        "password": Settings.CREODIAS_PASSWORD,
        "grant_type": "password",
    }
    try:
        r = requests.post(
            "https://auth.creodias.eu/auth/realms/DIAS/protocol/openid-connect/token",
            data=data,
        )
        r.raise_for_status()
    except Exception:
        raise Exception(
            f"Keycloak token creation failed. Reponse from the server was: {r.json()}"
        )
    return r.json()["access_token"]


def download_datasets(
        datasets: pd.DataFrame,
        download_dir: Union[Path,str],
        overwrite_existing_zips: Optional[bool] = False
    ) -> None:
    """
    Function for actual dataset download from CREODIAS.
    Requires valid CREODIAS username and password (to be
    specified in the BaseSettings)

    :param datasets:
        dataframe with results of CREODIAS Finder API request
        made by `query_creodias` function
    :param download_dir:
        directory where to store the downloaded files
    :param overwrite_existing_zips:
        if set to False (default), existing zip files in the
        ``download_dir`` are not overwritten. This feature can be
        useful to restart the downloader after a network connection
        timeout or similar. NOTE: Thhe function does not check if
        the existing zips are complete!
    """

    # get API token from CREODIAS
    keycloak_token = get_keycloak()

    # change into download directory
    os.chdir(str(download_dir))

    # loop over datasets to download them sequentially
    scene_counter = 1
    for _, dataset in datasets.iterrows():
        try:
            dataset_url = dataset.properties['services']['download']['url']
            response = requests.get(
                dataset_url,
                headers={'Authorization': f'Bearer {keycloak_token}'},
                stream=True
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f'Could not download {dataset.product_uri}: {e}')
            continue

        # download the data using the iter_content method (writes chunks to disk)
        # check if the dataset exists already and overwrite it only if defined by the user
        fname = dataset.dataset_name.replace('SAFE', 'zip')
        if Path(fname).exists():
            if not overwrite_existing_zips:
                logger.info(
                    f'{dataset.dataset_name} already downloaded - continue with next dataset'
                )
                continue
            else:
                logger.warning(f'Overwriting {dataset.dataset_name}')

        logger.info(f'Starting downloading {fname} ({scene_counter}/{datasets.shape[0]})')
        with open(fname, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                fd.write(chunk)
        logger.info(f'Finished downloading {fname} ({scene_counter}/{datasets.shape[0]})')
        scene_counter += 1
