"""
Functions to query Sentinel-1 specific metadata from the metadata DB.

Query criteria include

- the acquisition period (between a start and an end date)
- the geographic extent (bounding box)
- the instrument mode (e.g., IW -> Interferometric Wide Swath)
- the product type (e.g., GRD -> Ground Range Detected)

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
from eodal.metadata.database import S1_Raw_Metadata
from eodal.utils.exceptions import DataNotFoundError

Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


def find_raw_data_by_bbox(
    date_start: date,
    date_end: date,
    bounding_box: Union[Polygon, str],
    product_type: Optional[str] = "GRD",
    sensor_mode: Optional[str] = "IW",
) -> pd.DataFrame:
    """
    Queries the metadata DB by Sentinel-1 bounding box, time period, product type,
    and sensor mode. The returned data is ordered by sensing time in ascending
    order.

    NOTE:
        For the spatial query ``ST_Intersects`` is called.

    :param date_start:
        start date of the time period
    :param date_end:
        end date of the time period
    :param bounding_box:
        bounding box either as extended well-known text in geographic coordinates
        or as shapely ``Polygon`` in geographic coordinates (WGS84)
    :param product_type:
        Sentinel-1 product type. 'GRD' (Ground Range Detected) by default.
    :param sensor_mode:
        Sentinel-1 sensor mode. 'IW' (Interferometric Wide Swath) by default.
    :returns:
        `DataFrame` with references to found Sentinel-2 mapper
    """
    # convert shapely geometry into extended well-known text representation
    if isinstance(bounding_box, Polygon):
        bounding_box = f"SRID=4326;{bounding_box.wkt}"

    # formulate the query statement using the spatial and time period filter
    query_statement = (
        session.query(
            S1_Raw_Metadata.product_uri,
            S1_Raw_Metadata.scene_id,
            S1_Raw_Metadata.spacecraft_name,
            S1_Raw_Metadata.storage_share,
            S1_Raw_Metadata.storage_device_ip_alias,
            S1_Raw_Metadata.storage_device_ip,
            S1_Raw_Metadata.sensing_date,
            S1_Raw_Metadata.instrument_mode,
            S1_Raw_Metadata.sensing_orbit_direction,
            S1_Raw_Metadata.sensing_time,
            S1_Raw_Metadata.relative_orbit_start,
            S1_Raw_Metadata.relative_orbit_stop,
        )
        .filter(ST_Intersects(S1_Raw_Metadata.geom, ST_GeomFromText(bounding_box)))
        .filter(
            and_(
                S1_Raw_Metadata.sensing_date <= date_end,
                S1_Raw_Metadata.sensing_date >= date_start,
            )
        )
        .filter(S1_Raw_Metadata.instrument_mode == sensor_mode)
        .filter(S1_Raw_Metadata.product_type <= product_type)
        .order_by(S1_Raw_Metadata.sensing_date.asc())
        .statement
    )

    # read returned records in DataFrame and return
    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(f"Could not find Sentinel-1 data by bounding box: {e}")


def get_scene_metadata(product_uri: str) -> pd.DataFrame:
    """
    Returns the complete metadata record of a Sentinel-1 scene

    :param product_uri:
        unique product identifier. This corresponds to the .SAFE
        name of a Sentinel-1 dataset
    :returns:
        ``DataFrame`` with complete scene metadata
    """
    query_statement = (
        session.query(S1_Raw_Metadata)
        .filter(S1_Raw_Metadata.product_uri == product_uri)
        .statement
    )

    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(
            "Could not find Sentinel-2 scene with product_uri " f"{product_uri}: {e}"
        )
