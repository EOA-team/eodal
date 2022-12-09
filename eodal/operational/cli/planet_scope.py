'''
Operational Command-Line Utilities for Planet-Scope data
'''

from pathlib import Path
from typing import Any, Optional, Dict

from eodal.config.settings import get_settings
from eodal.metadata.planet_scope.database.querying import get_scene_metadata
from eodal.metadata.planet_scope.parsing import parse_metadata
from eodal.metadata.planet_scope.database.ingestion import metadata_dict_to_database

logger = get_settings().logger

def cli_ps_scenes_ingestion(
    ps_raw_data_archive: Path,
    path_options: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Loops over the Planet-Scope raw data archive and checks for each
    scene if it exists already in the eodal metadata DB. If not
    the entry is added.

    :param ps_raw_data_archive:
        Planet-Scope raw data archive to monitor.
    :param path_options:
        optional dictionary specifying storage_device_ip, storage_device_ip_alias
        (if applicable) and mount point in case the data is stored on a NAS
        and should be accessible from different operating systems or file systems
        with different mount points of the NAS share. If not provided, the absolute
        path of the dataset is used in the database.
    """
    # loop over all mapper
    for scene_dir in ps_raw_data_archive.iterdir():

        try:
            # query database for a given scene
            scene_metadata = parse_metadata(scene_dir)
            scene_df = get_scene_metadata(scene_id=scene_metadata['scene_id'])
            if scene_df.empty:
                # some path handling if required
                if path_options is not None:
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
                # ingest it into the database
                metadata_dict_to_database(scene_metadata)
                logger.info(f"Ingested scene metadata for {scene_metadata['scene_id']} into DB")
            else:
                logger.info(f"{scene_metadata['scene_id']} already in database")
        except Exception as e:
            logger.error(f"{scene_metadata['scene_id']} produced an error: {e}")
