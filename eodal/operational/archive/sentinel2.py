"""
Function to keep a local Sentinel-2 archive up-to-date by comparing data available
in your local archive for a given geographic region, time period and processing level
with records available from CREODIAS (user credentials required).

The function not only checks if CREODIAS has new datasets available, it also automatically
downloads them into a user-defined location.

IMPORTANT: In order to receive results the region (i.e., geographic extent) for which
to download data must be defined in the metadata DB.

IMPORTANT: CREODIAS does not allow more than 2000 records (each Sentinel-2 scene is a record)
to be queried at once. If you might exceed this threshold (e.g., your region is large and/or
your time period is long) split your query into smaller chunks by using, e.g., shorter time
periods for querying.

Copyright (C) 2022 Gregor Perich & Lukas Valentin Graf

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

import pandas as pd
import numpy as np

from datetime import date
from pathlib import Path
from typing import Optional

from eodal.utils.constants import ProcessingLevels
from eodal.downloader.sentinel2.creodias import query_creodias
from eodal.downloader.sentinel2.creodias import download_datasets

from eodal.downloader.sentinel2.utils import unzip_datasets
from eodal.metadata.database.querying import get_region
from eodal.metadata.sentinel2.database.querying import find_raw_data_by_bbox
from eodal.config import get_settings

logger = get_settings()


def pull_from_creodias(
    date_start: date,
    date_end: date,
    processing_level: ProcessingLevels,
    path_out: Path,
    region: str,
    cloud_cover_threshold: Optional[int] = 100,
    unzip: Optional[bool] = True,
    overwrite_existing_zips: Optional[bool] = False,
) -> pd.DataFrame:
    """
    Checks if CREODIAS has Sentinel-2 datasets not yet available locally
    and downloads these datasets from CREODIAS.

    NOTE:
        CREODIAS limits the maximum amount of datasets to download within a
        single query to somewhat around 2000. We therefore recommend to split
        the query into smaller ones if the query is likely to hit this limit.

    :param date start:
        Start date of the database & creodias query
    :param date end:
        End date of the database & creodias query
    :param processing_level:
        Select S2 processing level L1C or L2A
    :param path_out:
        Out directory where the additional data from CREODIAS should be
        downloaded to
    :param region:
        Region identifier of the Sentinel-2 archive. By region we mean a
        geographic extent (bounding box) in which the data is organized. The bounding
        box extent is taken from the metadata DB based on the region identifier.
    :param cloud_cover_threshold:
        cloud cover threshold (0-100%) to be used for CREODIAS query. Defaults
        to 100% (i.e., also completely cloudy scenes are downloaded).
    :param unzip:
        if True (default) datasets are unzipped and zip archives are deleted
    :param overwrite_existing_zips:
        if False (default) overwrites eventually existing zip files. If the download
        process was interrupted (e.g., due to a connection timeout) setting the flag
        to True can save time because datasets already downloaded are ignored. NOTE:
        The function does **not** check if a dataset was downloaded completely!
    :return:
        dataframe with references to downloaded datasets
    """

    # query database to get the bounding box of the selected region
    try:
        region_gdf = get_region(region)
    except Exception as e:
        logger.error(f"Failed to query region: {e}")
        return

    # parse the region's geometry as extended well-known-text
    bounding_box = region_gdf.geometry.iloc[0]
    bounding_box_ewkt = f"SRID=4326;{bounding_box.wkt}"

    # local database query to check what is already available locally
    try:
        meta_db_df = find_raw_data_by_bbox(
            date_start=date_start,
            date_end=date_end,
            processing_level=processing_level,
            bounding_box=bounding_box_ewkt,
        )
    except Exception as e:
        logger.error(f"Failed to query local datasets: {e}")
        return

    # set max_records to 2000 (CREODIAS currently does not allow more)
    max_records = 2000

    # check for available datasets
    datasets = query_creodias(
        start_date=date_start,
        end_date=date_end,
        max_records=max_records,
        processing_level=processing_level,
        bounding_box=bounding_box,
        cloud_cover_threshold=cloud_cover_threshold,
    )

    # get .SAFE datasets from CREODIAS
    datasets["product_uri"] = datasets.properties.apply(
        lambda x: Path(x["productIdentifier"]).name
    )

    # compare with records from local metadata DB and keep those records
    # not available locally
    missing_datasets = np.setdiff1d(
        datasets["product_uri"].values, meta_db_df["product_uri"].values
    )
    datasets_filtered = datasets[datasets.product_uri.isin(missing_datasets)]

    # download those scenes not available in the local database from Creodias
    download_datasets(
        datasets=datasets_filtered,
        download_dir=path_out,
        overwrite_existing_zips=overwrite_existing_zips,
    )

    # unzip datasets
    if unzip:
        unzip_datasets(download_dir=path_out)

    return datasets_filtered
