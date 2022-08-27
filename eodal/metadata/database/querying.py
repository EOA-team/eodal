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

import geopandas as gpd

from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker

from eodal.config import get_settings
from eodal.metadata.database import Regions, S2_Raw_Metadata
from eodal.utils.exceptions import DataNotFoundError, RegionNotFoundError

Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


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
