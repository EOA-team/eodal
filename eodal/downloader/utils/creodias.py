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
import pyotp
import requests
import shutil
import time

from pathlib import Path
from typing import Optional, Union
from eodal.config import get_settings

Settings = get_settings()
logger = Settings.logger

# fixed chunk size for downloading data
CHUNK_SIZE = 2096


def get_totp() -> str:
    """
    Get one-time access code using the TOTP algorithm to
    login into CREODIAS. The TOTP secret must have been
    set in the EOdal configurations using the `CREODIAS_TOTP_SECRET`
    variable.

    :return: one-time access key valid for a maximum of 30 seconds.
    """
    return pyotp.TOTP(Settings.CREODIAS_TOTP_SECRET).now()


def _get_keycloak(username: str, password: str) -> str:
    """
    Gets the keycloak token required by CREODIAS to sign requests.
    It uses the CREODIAS username, password and one-time access code
    (2FA) to authenticate at the Cloudferro Openid connector.

    :param username: CREODIAS username
    :param password: CREODIAS password
    :return: keycloak access token
    """
    # get one-time access code
    totp = get_totp()

    # prepare data for HTTP POST request
    data = {
        "client_id": "CLOUDFERRO_PUBLIC",
        "username": username,
        "password": password,
        "totp": int(totp),
        "grant_type": "password",
    }
    # request the token
    r = requests.post(
        "https://identity.cloudferro.com/auth/realms/Creodias-new/protocol/openid-connect/token",
        data=data,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_keycloak() -> str:
    """
    Gets the keycloak token required by CREODIAS to sign requests.
    It uses the CREODIAS username, password and one-time access code
    (2FA) to authenticate at the Cloudferro Openid connector.

    NOTE:
        A one-time access code is valid for 30 seconds. It can
        be only used once. This means, if one makes multiple requests
        for a keycloak token within <= 30 seconds, there will be a
        server error as the one-time access code has been consumed already.
        To make this behavior more stable, the application waits 31 seconds
        on error to request a new one-time access code (recursive call).

    :return: keycloak access token
    """
    # set user name and password from EOdal configuration
    username = Settings.CREODIAS_USER
    password = Settings.CREODIAS_PASSWORD
    try:
        return _get_keycloak(username, password)
    except Exception:
        # on error, sleep 31 seconds and then try again
        time.sleep(31)
        return get_keycloak()


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

    # change into download directory
    os.chdir(str(download_dir))

    # loop over datasets to download them sequentially
    scene_counter = 1
    for _, dataset in datasets.iterrows():
        try:
            # get API token from CREODIAS (only valid for a limited time)
            keycloak_token = get_keycloak()
            dataset_temp_url = dataset.properties["services"]["download"]["url"].split('/')[-1]
            dataset_url = f'{Settings.CREODIAS_ZIPPER_URL}/{dataset_temp_url}'
            response = requests.get(
                dataset_url,
                headers={"Authorization": f"Bearer {keycloak_token}"},
                stream=True,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Could not download {dataset_url}: {e}")
            continue

        # download the data using the iter_content method (writes chunks to disk)
        # check if the dataset exists already and overwrite it only if
        # defined by the user
        fname = dataset.dataset_name.replace("SAFE", "zip")
        if not fname.endswith("zip"):
            fname = fname + ".zip"
        if Path(fname).exists():
            if not overwrite_existing_zips:
                logger.info(
                    f"{dataset.dataset_name} already downloaded - " +
                    "continue with next dataset"
                )
                scene_counter += 1
                continue
            else:
                logger.warning(f"Overwriting {dataset.dataset_name}")

        logger.info(
            f"Starting downloading {fname} ({scene_counter}/{datasets.shape[0]})"
        )
        try:
            with open(fname, "wb") as fd:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    fd.write(chunk)
            logger.info(
                f"Finished downloading {fname} ({scene_counter}/{datasets.shape[0]})"
            )
        except Exception as e:
            # on error (e.g., broken network connection) delete the incomplete
            # zip archive and continue.
            shutil.rmtree(fname)
            logger.error(
                f'Downloading {fname} ({scene_counter}/{datasets.shape[0]}) ' +
                f'was interrupted.\n{e}\nRemoved broken zip.\n' +
                'Consider re-running the download.')
            
        scene_counter += 1


# # unit test (requires credentials for CREODIAS)
# if __name__ == '__main__':
#
#     from datetime import date
#     from eodal.downloader.sentinel2.creodias import query_creodias
#     from eodal.utils.constants.sentinel2 import ProcessingLevels
#     from shapely.geometry import box
#
#     bbox = box(*[8, 49, 9, 50])
#     start_date = date(2017, 10, 5)
#     end_date = date(2017, 10, 31)
#     max_records = 100
#     processing_level = ProcessingLevels.L2A
#     datasets = query_creodias(
#         start_date=start_date,
#         end_date=end_date,
#         max_records=max_records,
#         processing_level=processing_level,
#         bounding_box=bbox
#     )
#
#     download_dir = Path('/mnt/ides/Lukas/03_Debug/SAT/')
#     download_datasets(datasets=datasets, download_dir=download_dir, overwrite_existing_zips=False)
#
#     from eodal.downloader.utils.unzip_datasets import unzip_datasets
#
#     unzip_datasets(download_dir=download_dir, platform='S2', remove_zips=True)
