"""
Function to keep a local Sentinel (1/2) archive up-to-date by comparing data available
in your local archive for a given geographic region, time period, product type and
sensor mode.

The function not only checks if CREODIAS has new datasets available, it also automatically
downloads them into a user-defined location.

IMPORTANT:
    In order to receive results the region (i.e., geographic extent) for which
    to download data must be defined in the metadata DB.

IMPORTANT:
    CREODIAS does not allow more than 2000 records (each Sentinel scene is a record)
    to be queried at once. If you might exceed this threshold (e.g., your region is large and/or
    your time period is long) split your query into smaller chunks by using, e.g., shorter time
    periods for querying.

Copyright (C) 2022/23 Gregor Perich & Lukas Valentin Graf

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
import numpy as np
import shutil

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from eodal.config import get_settings
from eodal.downloader.sentinel1.creodias import query_creodias as s1_creodias_query
from eodal.downloader.sentinel2.creodias import query_creodias as s2_creodias_query
from eodal.downloader.utils.creodias import download_datasets
from eodal.downloader.utils import unzip_datasets
from eodal.metadata.database.querying import get_region
from eodal.metadata.sentinel1.database.ingestion import meta_df_to_database as s1_meta_to_db
from eodal.metadata.sentinel1.database.querying import find_raw_data_by_bbox as s1_db_query
from eodal.metadata.sentinel1.parsing import parse_s1_metadata
from eodal.metadata.sentinel2.database.ingestion import meta_df_to_database as s2_meta_to_db
from eodal.metadata.sentinel2.database.querying import find_raw_data_by_bbox as s2_db_query
from eodal.metadata.sentinel2.parsing import parse_s2_scene_metadata
from eodal.utils.constants import ProcessingLevels
from eodal.utils.exceptions import DataNotFoundError

settings = get_settings()
logger = settings.logger
max_records = settings.CREODIAS_MAX_RECORDS

required_subdirectories = {
    'sentinel1': ['measurement'],
    'sentinel2': ['GRANULE', 'AUX_DATA']
}

def pull_from_creodias(
    date_start: date,
    date_end: date,
    path_out: Path,
    region: str,
    sensor: str,
    unzip: Optional[bool] = True,
    overwrite_existing_zips: Optional[bool] = False,
    **kwargs
) -> pd.DataFrame:
    """
    Checks if CREODIAS has Sentinet datasets not yet available locally
    and downloads these datasets from CREODIAS.

    IMPORTANT:
        Unless specified otherwise, default products of the Sentinel
        platforms are used (e.g., GRD-IW for Sentinel-1, L2A for Sentinel-2)

    NOTE:
        CREODIAS limits the maximum amount of datasets to download within a
        single query to somewhat around 2000. We therefore recommend to split
        the query into smaller ones if the query is likely to hit this limit.

    :param date start:
        Start date of the database & creodias query
    :param date end:
        End date of the database & creodias query
    :param path_out:
        Out directory where the additional data from CREODIAS should be
        downloaded to
    :param region:
        Region identifier of the Sentinel-2 archive. By region we mean a
        geographic extent (bounding box) in which the data is organized. The bounding
        box extent is taken from the metadata DB based on the region identifier.
    :param sensor:
        name of the sensor to download data. Currently, `sentinel1` and `sentinel2`
        are supported.
    :param unzip:
        if True (default) datasets are unzipped and zip archives are deleted
    :param overwrite_existing_zips:
        if False (default) overwrites eventually existing zip files. If the download
        process was interrupted (e.g., due to a connection timeout) setting the flag
        to True can save time because datasets already downloaded are ignored. NOTE:
        The function does **not** check if a dataset was downloaded completely!
    :param kwargs:
        optional key-word arguments to pass to 
        `~eodal.downloader.sentinel1.creodias.query_creodias` such sensor_mode and
        product_type
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
    if sensor == 'sentinel1':
        try:
            product_type = kwargs.get('product_type', 'GRD')
            sensor_mode = kwargs.get('sensor_mode', 'IW')
            meta_db_df = s1_db_query(
                date_start=date_start,
                date_end=date_end,
                product_type=product_type,
                sensor_mode=sensor_mode,
                bounding_box=bounding_box_ewkt,
            )

            # check for available datasets on CREODIAS
            datasets = s1_creodias_query(
                start_date=date_start,
                end_date=date_end,
                max_records=max_records,
                bounding_box=bounding_box,
                product_type=product_type,
                sensor_mode=sensor_mode
            )
        except Exception as e:
            logger.error(f'Failed to update Sentinel1 archive: {e}')
            return pd.DataFrame([])

    elif sensor == 'sentinel2':
        try:
            processing_level = kwargs.get('processing_level', ProcessingLevels.L2A)
            cloud_cover_threshold = kwargs.get('cloud_cover_threshold', 100)
            meta_db_df = s2_db_query(
                date_start=date_start,
                date_end=date_end,
                processing_level=processing_level,
                bounding_box=bounding_box_ewkt,
            )

            # check for available datasets
            datasets = s2_creodias_query(
                start_date=date_start,
                end_date=date_end,
                max_records=max_records,
                processing_level=processing_level,
                bounding_box=bounding_box,
                cloud_cover_threshold=cloud_cover_threshold,
            )
        except Exception as e:
            logger.error(f'Failed to update Sentinel2 archive: {e}')
            return pd.DataFrame([])

    else:
        raise ValueError(f'Unknown sensor: {sensor}')

    # get .SAFE datasets from CREODIAS
    datasets["product_uri"] = datasets.properties.apply(
        lambda x: Path(x["productIdentifier"]).name
    )

    # compare with records from local metadata DB and keep those records
    # not available locally
    missing_datasets = np.setdiff1d(
        datasets["product_uri"].values,
        meta_db_df["product_uri"].values
    )
    datasets_filtered = datasets[datasets.product_uri.isin(missing_datasets)].copy()

    # download those mapper not available in the local database from CREODIAS
    download_datasets(
        datasets=datasets_filtered,
        download_dir=path_out,
        overwrite_existing_zips=overwrite_existing_zips,
    )

    # unzip datasets
    if unzip:
        if sensor == 'sentinel1':
            platform = 'S1'
        elif sensor == 'sentinel2':
            platform = 'S2'
        try:
            unzip_datasets(download_dir=path_out, platform=platform)
        except DataNotFoundError as e:
            logger.warn(e)

    return datasets_filtered

def sentinel_creodias_update(
    sentinel_raw_data_archive: Path,
    region: str,
    path_options: Optional[Dict[str, str]] = None,
    overwrite_existing_zips: Optional[bool] = False,
    **kwargs
) -> None:
    """
    Loops over an existing Sentinel rawdata (i.e., *.SAFE datasets) archive
    and checks the datasets available locally with those datasets available at
    CREODIAS for a defined Area of Interest (AOI) and time period (we store the
    data year by year, therefore, we always check an entire year).

    The missing data (if any) is downloaded into a temporary download directory
    `temp_dl` and unzip. The data is then copied into the actual Sentinel
    archive and the metadata is extracted and ingested into the metadata base.

    IMPORTANT:
        Requires a CREODIAS user account (user name and password).

    IMPORTANT:
        For database ingestion it is important to map the paths correctly
        and store them in the database in a way that allows accessing the data from
        all your system components (``file_system_options``).

    * In the easiest case, this the absolute path to the datasets (or URI)
    * If your data is stored on a NAS, you might specify the address of the NAS
      in the variable `storage_device_ip` and provide a `mount_point`, i.e.,
      the path (or drive on Windows) where the NAS is mounted into your local
      file system. Also aliasing of the is supported (`storage_device_ip_alias`),
      however, if possible try to avoid it.


    :param sentinel_raw_data_archive:
        Sentinel (1 or 2) raw data archive (containing *.SAFE datasets) to monitor.
        Existing datasets must have been already ingested into the metadata
        base!
    :param region:
        eodal's archive philosophy organizes datasets by geographic regions.
        Each region is identified by a unique region identifier (e.g., we use
        `CH` for Switzerland) and has a geographic extent described by a polygon
        geometry (bounding box) in geographic coordinates (WGS84). The geometry
        also defines the geographic dimension of the CREODIAS query. It is
        stored as a entry in the metadata base.
    :param processing_level:
        Sentinel-2 processing level (L1C or L2A) to check.
    :param cloud_cover_threshold:
        optional cloud cover threshold to filter out to cloudy mapper as integer
        between 0 and 100%.
    :param path_options:
        optional dictionary specifying storage_device_ip, storage_device_ip_alias
        (if applicable) and mount point in case the data is stored on a NAS
        and should be accessible from different operating systems or file systems
        with different mount points of the NAS share. If not provided, the absolute
        path of the dataset is used in the database.
    :param overwrite_existing_zips:
        if False (default) overwrites eventually existing zip files. If the download
        process was interrupted (e.g., due to a connection timeout) setting the flag
        to True can save time because datasets already downloaded are ignored. NOTE:
        The function does **not** check if a dataset was downloaded completely!

    Example
    -------

    .. code-block:: python

    from pathlib import Path
    from eodal.utils.constants import ProcessingLevels

    # this example shows the workflow for Sentinel-2 (Sentinel-1 would also be possible
    # but requires slightly different inputs)
    sensor = 'sentinel2'
    
    # define processing level (usually L2A but also L1C works)
    processing_level = ProcessingLevels.L2A

    # specifiy region, we use Switzerland (the extent of Switzerland is defined in the database)
    region = 'CH'

    # the archive should be always mounted in the same way for each user
    user_name = '<your_username>'
    s2_raw_data_archive = Path(f'/home/{user_name}/public/Evaluation/Satellite_data/Sentinel-2/Rawdata')

    # file-system specific handling: this allows to store the paths in the database
    # in such way that the dataset paths can be found from Linux and Windows machines
    file_system_options = {
        'storage_device_ip': '<your_nas_ip>',
        'storage_device_ip_alias': '<alternative_nas_ip_if_any',
        'mount_point': f'/home/{user_name}/public/'
    }

    sentinel_creodias_update(
        s2_raw_data_archive=s2_raw_data_archive,
        region=region,
        path_options=file_system_options,
        sensor='sentinel2',
        processing_level=processing_level
    )

    """
    sensor = kwargs.get('sensor')
    if sensor is None:
        raise TypeError('Sensor is required')
    if sensor not in ['sentinel1', 'sentinel2']:
        raise ValueError(f'Unknown sensor: {sensor}')

    # since the data is stored by year (each year is a single sub-directory) we
    # can simple loop over the sub-directories and do the check
    for path in Path(sentinel_raw_data_archive).iterdir():
        if path.is_dir():
            # get year automatically
            try:
                year = int(path.name)
            except ValueError:
                logger.info(f'{path.name} is not provided in YYYY format - skipping')
                continue

            # create temporary download directory
            path_out = path.joinpath(f"temp_dl_{year}")
            path_out.mkdir(exist_ok=True)

            # download data from CREODIAS
            downloaded_ds = pull_from_creodias(
                date_start=date(year,1,1),
                date_end=date(year,12,31),
                path_out=path_out,
                region=region,
                overwrite_existing_zips=overwrite_existing_zips,
                **kwargs
            )

            if downloaded_ds.empty:
                logger.info(f"No new datasets found for year {year} on CREODIAS")
                continue

            # move the datasets into the actual SAT archive (on level up)
            parent_dir = path_out.parent
            for _, record in downloaded_ds.iterrows():
                # check if the record exists first
                if not path_out.joinpath(record.dataset_name).exists():
                    logger.warn(f'{record.dataset_name} does not exist')
                    continue

                try:
                    shutil.move(record.dataset_name, "..")
                    logger.info(f"Moved {record.dataset_name} to {parent_dir}")
                except Exception as e:
                    logger.error(f'Could not move {record.dataset_name}: {e}')
                    continue

                # check if the SAFE folder is complete
                for required_subdir in required_subdirectories[sensor]:
                    if not parent_dir.joinpath(record.dataset_name).joinpath(required_subdir).exists():
                        logger.error(f'{record.dataset_name} has no sub-directory {required_subdir}')
                        shutil.rmtree(parent_dir.joinpath(record.dataset_name))
                        continue

                # once the dataset is moved successfully parse its metadata and
                # ingest it into the database
                in_dir = path.joinpath(record.dataset_name)
                try:
                    if sensor == 'sentinel1':
                        scene_metadata = parse_s1_metadata(in_dir=in_dir)
                    elif sensor == 'sentinel2':
                        scene_metadata, _ = parse_s2_scene_metadata(in_dir=in_dir)
                except Exception as e:
                    logger.error(f'Parsing of metadata of {record.dataset_name} failed: {e}')
                    shutil.rmtree(in_dir)
                    continue

                # some path handling if required
                if path_options != {}:
                    try:
                        scene_metadata["storage_device_ip"] = path_options.get(
                            "storage_device_ip", ""
                        )
                        scene_metadata["storage_device_ip_alias"] = path_options.get(
                            "storage_device_ip_alias", ""
                        )
                        mount_point = path_options.get("mount_point", "")
                        mount_point_replacement = path_options.get(
                            "mount_point_replacement", ""
                        )
                        scene_metadata["storage_share"] = scene_metadata[
                            "storage_share"
                        ].replace(mount_point, mount_point_replacement)
                    except Exception as e:
                        logger.error(f'Handling path options for {record.dataset_name} failed: {e}')
                        shutil.rmtree(in_dir)
                        continue

                    # database insert
                    try:
                        scene_metadata = pd.DataFrame([scene_metadata])
                        if sensor == 'sentinel1':
                            s1_meta_to_db(meta_df=scene_metadata)
                        elif sensor == 'sentinel2':
                            s2_meta_to_db(meta_df=scene_metadata)
                        logger.info(
                            f"Ingested scene metadata for {record.dataset_name} into DB"
                        )
                    except Exception as e:
                        logger.error(
                            f'Could not ingest scene metadata for {record.dataset_name} into DB: {e}'
                        )
                        shutil.rmtree(in_dir)
                        continue

            # delete the temp_dl directory
            shutil.rmtree(path_out)
