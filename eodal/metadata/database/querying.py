"""
Functions to query remote sensing platform independent metadata from the metadata DB.

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

import geopandas as gpd

from datetime import datetime
from geoalchemy2.functions import ST_Intersects
from geoalchemy2.functions import ST_GeomFromText
from shapely.geometry import Polygon
from sqlalchemy import asc, and_, create_engine, inspect
from sqlalchemy.orm.session import sessionmaker
from typing import List

from eodal.config import get_settings
from eodal.mapper.filter import Filter
from eodal.metadata.database import Regions, S2_Raw_Metadata
from eodal.utils.exceptions import DataNotFoundError, RegionNotFoundError

Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()

# map platforms to metadata models
platform_mapping = {
    "sentinel1": "S1_Raw_Metadata",
    "sentinel2": "S2_Raw_Metadata",
    "ps_superdove": "PS_SuperDove_Metadata",
}


def get_region(region: str) -> gpd.GeoDataFrame:
    """
    Queries the metadata DB for a specific region and its geographic
    extent.

    :param region:
        unique region identifier

    :return:
        `GeoDataFrame` with the geometry of the queried region
    """
    query_statement = (
        session.query(Regions.geom, Regions.region_uid)
        .filter(Regions.region_uid == region)
        .statement
    )
    try:
        return gpd.read_postgis(query_statement, session.bind)
    except Exception as e:
        raise RegionNotFoundError(f"{region} not found: {e}")


def find_raw_data_by_bbox(
    platform: str,
    time_start: datetime,
    time_end: datetime,
    bounding_box: Polygon,
    metadata_filters: List[Filter],
) -> gpd.GeoDataFrame:
    """
    Query the metadata DB by a geographic bounding box, time period
    and custom filters
    """
    # get the DB table for a given platform
    inspector = inspect(engine)
    db_tables = inspector.get_table_names(schema=Settings.DEFAULT_SCHEMA)
    # the table names follow the scheme <platform>_raw_metadata
    platform_table = f"{platform}_raw_metadata"
    if platform_table not in db_tables:
        raise ValueError(f"{platform} was not found in database")

    # loop over metadata filters and construct the sqlalchemy expressions
    filter_str = ""
    for metadata_filter in metadata_filters:
        value = metadata_filter.value
        if type(metadata_filter.value) == str:
            value = f'"{metadata_filter.value}"'
        filter_str += (
            f".filter(db_model.{metadata_filter.entity} "
            + f"{metadata_filter.operator} {value})"
        )

    # build the query using "db_model" as a placeholder for the actual db-model
    # of the platform
    bounding_box_wkt = f"SRID=4326;{bounding_box.wkt}"
    query_statement_exc = (
        f"""
        (session.query(db_model)
        .filter(ST_Intersects(db_model.geom, ST_GeomFromText(bounding_box_wkt)))
        .filter(
            and_(
                db_model.sensing_time <= time_end,
                db_model.sensing_time >= time_start,
            )
        )
        """
        + filter_str
        + """
        .order_by(db_model.sensing_date.asc())
        ).statement
        """
    )
    exec(
        f"from eodal.metadata.database import {platform_mapping[platform]} as db_model"
    )
    query_statement = eval(query_statement_exc.replace("\n", "").replace(" ", ""))

    # read returned records as a GeoDataFrame and return
    try:
        return gpd.read_postgis(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(f"Could not find {platform} data by bounding box: {e}")


def get_s2_tile_footprint(tile_name: str) -> gpd.GeoDataFrame:
    """
    Queries the geographic extent of a Sentinel-2 tile

    :param sensor:
        name of the sensor the tiling scheme belongs to (e.g.,
        'sentinel2')
    :param tile_name:
        name of the tile in the tiling scheme (e.g., 'T32TMT')
    :returns:
        extent of the tile in geographic coordinates (WGS84)
    """
    query_statement = (
        session.query(S2_Raw_Metadata.geom)
        .filter(S2_Raw_Metadata.tile_id == tile_name)
        .distinct()
        .statement
    )
    try:
        return gpd.read_postgis(query_statement, session.bind)
    except Exception as e:
        raise DataNotFoundError(f"{tile_name} not found: {e}")
