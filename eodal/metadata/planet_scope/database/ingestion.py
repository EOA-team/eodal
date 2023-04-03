"""
Ingestion of PlanetScope metadata into the metadata DB.

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

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker

from eodal.metadata.database.db_model import PS_SuperDove_Metadata
from eodal.config import get_settings

Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


def metadata_dict_to_database(metadata: dict) -> None:
    """
    Inserts extracted metadata into the meta database

    :param metadata:
        dictionary with the extracted metadata
    """

    # convert keys to lower case
    metadata = {k.lower(): v for k, v in metadata.items()}
    try:
        session.add(PS_SuperDove_Metadata(**metadata))
        session.flush()
    except Exception as e:
        logger.error(f"Database INSERT failed: {e}")
        session.rollback()
    session.commit()


if __name__ == "__main__":
    from pathlib import Path
    from eodal.metadata.planet_scope.parsing import parse_metadata

    in_dir = Path("/mnt/ides/Lukas/software/eodal/data/20220414_101133_47_227b")
    metadata = parse_metadata(in_dir)
    metadata_dict_to_database(metadata)
