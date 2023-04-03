"""
Functions to query PlanetScope specific metadata from the metadata DB.

Query criteria include

- the acquisition period (between a start and an end date)
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
from eodal.metadata.database.db_model import PS_SuperDove_Metadata
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
    cloud_cover_threshold: Optional[Union[int, float]] = 100,
) -> pd.DataFrame:
    """
    Queries the metadata DB by Planet-Scope bounding box, time period and cloud cover.
    The returned data is ordered by sensing time in ascending order.

    NOTE:
        For the spatial query ``ST_Intersects`` is called.

    :param date_start:
        start date of the time period
    :param date_end:
        end date of the time period
    :param bounding_box_wkt:
        bounding box either as extended well-known text in geographic coordinates
        or as shapely ``Polygon`` in geographic coordinates (WGS84)
    :param cloud_cover_threshold:
        optional cloud cover threshold to filter datasets by scene cloud coverage.
        Must be provided as number between 0 and 100%.
    :returns:
        dataframe with references to found Planet-Scope mapper
    """

    # convert shapely geometry into extended well-known text representation
    if isinstance(bounding_box, Polygon):
        bounding_box = f"SRID=4326;{bounding_box.wkt}"

    # formulate the query statement using the spatial and time period filter
    query_statement = (
        session.query(
            PS_SuperDove_Metadata.scene_id,
            PS_SuperDove_Metadata.satellite_id,
            PS_SuperDove_Metadata.storage_share,
            PS_SuperDove_Metadata.storage_device_ip_alias,
            PS_SuperDove_Metadata.storage_device_ip,
            PS_SuperDove_Metadata.sensing_time,
            PS_SuperDove_Metadata.cloud_percent,
            PS_SuperDove_Metadata.cloud_cover,
            PS_SuperDove_Metadata.sun_azimuth,
            PS_SuperDove_Metadata.sun_elevation,
            PS_SuperDove_Metadata.satellite_azimuth,
            PS_SuperDove_Metadata.view_angle,
        )
        .filter(
            ST_Intersects(PS_SuperDove_Metadata.geom, ST_GeomFromText(bounding_box))
        )
        .filter(
            and_(
                PS_SuperDove_Metadata.sensing_date <= date_end,
                PS_SuperDove_Metadata.sensing_date >= date_start,
            )
        )
        .filter(PS_SuperDove_Metadata.cloud_percent <= cloud_cover_threshold)
        .order_by(PS_SuperDove_Metadata.sensing_time.asc())
        .statement
    )

    # read returned records in DataFrame and return
    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(
            f"Could not find Planet-Scope data by bounding box: {e}"
        )


def get_scene_metadata(scene_id: str) -> pd.DataFrame:
    """
    Returns the complete metadata record of a Planet-Scope scene

    :param product_uri:
        unique scene identifier provided by Planet in the metadata *.json file
    :returns:
        ``DataFrame`` with complete scene metadata
    """
    query_statement = (
        session.query(PS_SuperDove_Metadata)
        .filter(PS_SuperDove_Metadata.scene_id == scene_id)
        .statement
    )

    try:
        return pd.read_sql(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(
            "Could not find Planet-Scope scene with product_uri " f"{scene_id}: {e}"
        )
