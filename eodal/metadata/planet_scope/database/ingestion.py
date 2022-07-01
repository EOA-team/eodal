'''
Ingestion of PlanetScope metadata into the metadata DB
'''

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

if __name__ == '__main__':

    from pathlib import Path
    from eodal.metadata.planet_scope.parsing import parse_metadata
    
    in_file = Path(
        '/mnt/ides/Lukas/software/eodal/data/20220414_101133_47_227b/20220414_101133_47_227b_metadata.json'
    )
    metadata = parse_metadata(in_file)
    metadata_dict_to_database(metadata)


    
