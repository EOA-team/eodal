"""
Utility functions for downloading data from CREODIAS

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
import pandas as pd
import requests

from pathlib import Path
from typing import Optional, Union
from eodal.config import get_settings

Settings = get_settings()
logger = Settings.logger

# fixed chunk size for downloading data
CHUNK_SIZE = 2096


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
    download_dir: Union[Path, str],
    overwrite_existing_zips: Optional[bool] = False,
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
            dataset_url = dataset.properties["services"]["download"]["url"]
            response = requests.get(
                dataset_url,
                headers={"Authorization": f"Bearer {keycloak_token}"},
                stream=True,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Could not download {dataset.product_uri}: {e}")
            continue

        # download the data using the iter_content method (writes chunks to disk)
        # check if the dataset exists already and overwrite it only if defined by the user
        fname = dataset.dataset_name.replace("SAFE", "zip")
        if Path(fname).exists():
            if not overwrite_existing_zips:
                logger.info(
                    f"{dataset.dataset_name} already downloaded - continue with next dataset"
                )
                continue
            else:
                logger.warning(f"Overwriting {dataset.dataset_name}")

        logger.info(
            f"Starting downloading {fname} ({scene_counter}/{datasets.shape[0]})"
        )
        with open(fname, "wb") as fd:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                fd.write(chunk)
        logger.info(
            f"Finished downloading {fname} ({scene_counter}/{datasets.shape[0]})"
        )
        scene_counter += 1
