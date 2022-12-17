"""
Functions to insert Sentinel-2 specific metadata into the metadata DB

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

from typing import Optional
from typing import List
from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker

from eodal.metadata.database.db_model import S2_Raw_Metadata
from eodal.metadata.database.db_model import S2_Processed_Metadata
from eodal.config import get_settings


Settings = get_settings()
logger = Settings.logger

DB_URL = f"postgresql://{Settings.DB_USER}:{Settings.DB_PW}@{Settings.DB_HOST}:{Settings.DB_PORT}/{Settings.DB_NAME}"
engine = create_engine(DB_URL, echo=Settings.ECHO_DB)
session = sessionmaker(bind=engine)()


def meta_df_to_database(
    meta_df: pd.DataFrame, raw_metadata: Optional[bool] = True
) -> None:
    """
    Once the metadata from one or more mapper have been extracted
    the data can be ingested into the metadata base (strongly
    recommended).

    This function takes a metadata frame extracted from "raw" or
    "processed" (i.e., after spatial resampling, band stacking and merging)
    Sentinel-2 data and inserts the data via pandas intrinsic
    sql-methods into the database.

    :param meta_df:
        data frame with metadata of one or more mapper to insert
    :param raw_metadata:
        If set to False, assumes the metadata is about processed
        products
    """

    meta_df.columns = meta_df.columns.str.lower()
    for _, record in meta_df.iterrows():
        metadata = record.to_dict()
        try:
            if raw_metadata:
                session.add(S2_Raw_Metadata(**metadata))
            else:
                session.add(S2_Processed_Metadata(**metadata))
            session.flush()
        except Exception as e:
            logger.error(f"Database INSERT failed: {e}")
            session.rollback()
    session.commit()


def metadata_dict_to_database(metadata: dict) -> None:
    """
    Inserts extracted metadata into the meta database

    :param metadata:
        dictionary with the extracted metadata
    """

    # convert keys to lower case
    metadata = {k.lower(): v for k, v in metadata.items()}
    try:
        session.add(S2_Raw_Metadata(**metadata))
        session.flush()
    except Exception as e:
        logger.error(f"Database INSERT failed: {e}")
        session.rollback()
    session.commit()


def update_raw_metadata(meta_df: pd.DataFrame, columns_to_update: List[str]) -> None:
    """
    Function to update one or more atomic columns
    in the metadata base. The table primary keys 'scene_id'
    and 'product_uri' must be given in the passed dataframe.

    :param meta_df:
        dataframe with metadata entries to update. Must
        contain the two primary key columns 'scene_id' and
        'product_uri'
    :param columns_to_update:
        List of columns to update. These must be necessarily
        atomic attributes of the raw_metadata table.
    """

    meta_df.columns = meta_df.columns.str.lower()

    try:
        for _, record in meta_df.iterrows():
            # save values to update in dict
            value_dict = record[columns_to_update].to_dict()
            for key, val in value_dict.items():
                meta_db_rec = (
                    session.query(S2_Raw_Metadata)
                    .filter(
                        and_(
                            S2_Raw_Metadata.scene_id == record.scene_id,
                            S2_Raw_Metadata.product_uri == record.product_uri,
                        )
                    )
                    .first()
                )
                meta_db_rec.__getattribute__(key)
                setattr(meta_db_rec, key, val)
                session.flush()
            session.commit()
    except Exception as e:
        logger.error(f"Database UPDATE failed: {e}")
        session.rollback()
