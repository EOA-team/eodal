"""
Functions to query Sentinel-2 specific metadata from the metadata DB.

Query criteria include

- the processing level (either L1C or L2A for ESA derived Sentinel-2 data)
- the acquisition period (between a start and an end dat)
- the tile (e.g., "T32TLT") or a bounding box (provided as extended well-known-text)
- the scene-wide cloud coverage (derived from the scene metadata); this is optional.

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

from datetime import date
from geoalchemy2.functions import ST_Intersects
from geoalchemy2.functions import ST_GeomFromText
from shapely.geometry import Polygon
from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy.orm import sessionmaker
from typing import Optional
from typing import Union

from eodal.config import get_settings
from eodal.metadata.database import S2_Raw_Metadata
from eodal.utils.constants import ProcessingLevels
from eodal.utils.constants.sentinel2 import ProcessingLevelsDB
from eodal.utils.exceptions import DataNotFoundError

Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


def find_raw_data_by_bbox(
    date_start: date,
    date_end: date,
    processing_level: ProcessingLevels,
    bounding_box: Union[Polygon, str],
    cloud_cover_threshold: Optional[Union[int, float]] = 100,
) -> pd.DataFrame:
    """
    Queries the metadata DB by Sentinel-2 bounding box, time period and processing
    level (and cloud cover). The returned data is ordered by sensing time in
    ascending order.

    NOTE:
        For the spatial query ``ST_Intersects`` is called.

    :param date_start:
        start date of the time period
    :param date_end:
        end date of the time period
    :param processing_level:
        Sentinel-2 processing level
    :param bounding_box_wkt:
        bounding box either as extended well-known text in geographic coordinates
        or as shapely ``Polygon`` in geographic coordinates (WGS84)
    :param cloud_cover_threshold:
        optional cloud cover threshold to filter datasets by scene cloud coverage.
        Must be provided as number between 0 and 100%.
    :returns:
        dataframe with references to found Sentinel-2 mapper
    """

    # translate processing level
    processing_level_db = ProcessingLevelsDB[processing_level.name]

    # convert shapely geometry into extended well-known text representation
    if isinstance(bounding_box, Polygon):
        bounding_box = f"SRID=4326;{bounding_box.wkt}"

    # formulate the query statement using the spatial and time period filter
    query_statement = (
        session.query(
            S2_Raw_Metadata.product_uri,
            S2_Raw_Metadata.scene_id,
            S2_Raw_Metadata.tile_id,
            S2_Raw_Metadata.spacecraft_name,
            S2_Raw_Metadata.storage_share,
            S2_Raw_Metadata.storage_device_ip_alias,
            S2_Raw_Metadata.storage_device_ip,
            S2_Raw_Metadata.sensing_date,
            S2_Raw_Metadata.cloudy_pixel_percentage,
            S2_Raw_Metadata.sensing_orbit_number,
            S2_Raw_Metadata.sensing_time,
            S2_Raw_Metadata.epsg,
            S2_Raw_Metadata.sun_azimuth_angle,
            S2_Raw_Metadata.sun_zenith_angle,
            S2_Raw_Metadata.sensor_azimuth_angle,
            S2_Raw_Metadata.sensor_zenith_angle,
        )
        .filter(ST_Intersects(S2_Raw_Metadata.geom, ST_GeomFromText(bounding_box)))
        .filter(
            and_(
                S2_Raw_Metadata.sensing_date <= date_end,
                S2_Raw_Metadata.sensing_date >= date_start,
            )
        )
        .filter(S2_Raw_Metadata.processing_level == processing_level_db)
        .filter(S2_Raw_Metadata.cloudy_pixel_percentage <= cloud_cover_threshold)
        .order_by(S2_Raw_Metadata.sensing_date.asc())
        .statement
    )

    # read returned records in DataFrame and return
    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(f"Could not find Sentinel-2 data by bounding box: {e}")


def find_raw_data_by_tile(
    date_start: date,
    date_end: date,
    processing_level: ProcessingLevels,
    tile: str,
    cloud_cover_threshold: Optional[Union[int, float]] = 100,
) -> pd.DataFrame:
    """
    Queries the metadata DB by Sentinel-2 tile, time period and processing
    level.

    :param date_start:
        start date of the time period
    :param date_end:
        end date of the time period
    :param processing_level:
        Sentinel-2 processing level
    :param tile:
        Sentinel-2 tile
    :param cloud_cover_threshold:
        optional cloud cover threshold to filter datasets by scene cloud coverage.
        Must be provided as number between 0 and 100%.
    :returns:
        dataframe with references to found Sentinel-2 mapper
    """

    # translate processing level
    processing_level_db = ProcessingLevelsDB[processing_level.name]

    query_statement = (
        session.query(
            S2_Raw_Metadata.product_uri,
            S2_Raw_Metadata.scene_id,
            S2_Raw_Metadata.spacecraft_name,
            S2_Raw_Metadata.storage_share,
            S2_Raw_Metadata.storage_device_ip_alias,
            S2_Raw_Metadata.storage_device_ip,
            S2_Raw_Metadata.sensing_date,
            S2_Raw_Metadata.cloudy_pixel_percentage,
            S2_Raw_Metadata.sensing_orbit_number,
            S2_Raw_Metadata.sensing_time,
            S2_Raw_Metadata.cloudy_pixel_percentage,
            S2_Raw_Metadata.epsg,
            S2_Raw_Metadata.sun_azimuth_angle,
            S2_Raw_Metadata.sun_zenith_angle,
            S2_Raw_Metadata.sensor_azimuth_angle,
            S2_Raw_Metadata.sensor_zenith_angle,
        )
        .filter(S2_Raw_Metadata.tile_id == tile)
        .filter(
            and_(
                S2_Raw_Metadata.sensing_date <= date_end,
                S2_Raw_Metadata.sensing_date >= date_start,
            )
        )
        .filter(S2_Raw_Metadata.processing_level == processing_level_db)
        .filter(S2_Raw_Metadata.cloudy_pixel_percentage <= cloud_cover_threshold)
        .order_by(S2_Raw_Metadata.sensing_date.desc())
        .statement
    )

    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(f"Could not find Sentinel-2 data by tile: {e}")


def get_scene_metadata(product_uri: str) -> pd.DataFrame:
    """
    Returns the complete metadata record of a Sentinel-2 scene

    :param product_uri:
        unique product identifier. This corresponds to the .SAFE
        name of a Sentinel-2 dataset
    :returns:
        ``DataFrame`` with complete scene metadata
    """
    query_statement = (
        session.query(S2_Raw_Metadata)
        .filter(S2_Raw_Metadata.product_uri == product_uri)
        .statement
    )

    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(
            "Could not find Sentinel-2 scene with product_uri " f"{product_uri}: {e}"
        )
