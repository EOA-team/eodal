'''
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
'''

import geopandas as gpd

from sqlalchemy import create_engine

from eodal.metadata.database import Regions
from eodal.utils.exceptions import RegionNotFoundError
from eodal.config import get_settings
from sqlalchemy.orm.session import sessionmaker


Settings = get_settings()
logger = Settings.logger

DB_URL = f'postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}'
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


def get_region(
        region: str
    ) -> gpd.GeoDataFrame:
    """
    Queries the metadata DB for a specific region and its geographic
    extent.

    :param region:
        unique region identifier

    :return:
        geodataframe with the geometry of the queried region
    """

    query_statement = session.query(
        Regions.geom,
        Regions.region_uid
    ).filter(
        Regions.region_uid == region
    ).statement

    try:
        return gpd.read_postgis(query_statement, session.bind)

    except Exception as e:
        raise RegionNotFoundError(f'{region} not found: {e}')
