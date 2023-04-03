"""
This module contains functions to extract relevant scene-specific
Sentinel-1 metadata

Copyright (C) 2022 Gregor Perich

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

import glob
import numpy as np
import os
import pandas as pd
import time

from datetime import date, datetime
from pathlib import Path
from shapely.geometry import Polygon
from shapely.geometry.polygon import LinearRing
from typing import Dict, Optional
from xml.dom import minidom

from eodal.config import get_settings
from eodal.utils.exceptions import DataNotFoundError, InputError

Settings = get_settings()
logger = Settings.logger


def parse_s1_metadata(in_dir: Path) -> Dict:
    """
    Parses the metadata found in the "manifest.safe" document of S1_IW_GRDH Level-1 products and
    writes them into a Python dictionary

    :param in_dir:
        file-path of the file you want to extract the metadata from
    :returns:
        Dictionary containing the metadata of the passed S1 scene ready for DB ingestion
    """
    in_file = in_dir.joinpath("manifest.safe").as_posix()

    # parse Document Object Model (DOM) file from xml
    domfile = minidom.parse(in_file)
    metadata = dict()

    # extract uid from SAFE filename
    safe_file = in_dir.name
    uid_str = safe_file.split(".")[0]

    metadata["scene_id"] = uid_str
    metadata["product_uri"] = safe_file

    # =============== variables to fill from the xml =======================
    # spacecraft_name
    for elem in domfile.getElementsByTagName("safe:platform"):
        s1_name = elem.getElementsByTagName("safe:familyName")[0].firstChild.nodeValue
        s1_num = elem.getElementsByTagName("safe:number")[0].firstChild.nodeValue
    metadata["spacecraft_name"] = s1_name + s1_num

    # sensing_orbit_number
    for elem in domfile.getElementsByTagName("safe:orbitNumber"):
        if elem.getAttributeNode("type").nodeValue == "start":
            start_orbit = elem.firstChild.nodeValue
        if elem.getAttributeNode("type").nodeValue == "stop":
            stop_orbit = elem.firstChild.nodeValue
    metadata["sensing_orbit_start"] = int(start_orbit)
    metadata["sensing_orbit_stop"] = int(stop_orbit)

    # relative_orbit_number
    for elem in domfile.getElementsByTagName("safe:relativeOrbitNumber"):
        if elem.getAttributeNode("type").nodeValue == "start":
            start_orbit = elem.firstChild.nodeValue
        if elem.getAttributeNode("type").nodeValue == "stop":
            stop_orbit = elem.firstChild.nodeValue

    metadata["relative_orbit_start"] = int(start_orbit)
    metadata["relative_orbit_stop"] = int(stop_orbit)

    # sensing_orbit_direction
    for elem in domfile.getElementsByTagName("s1:pass"):
        direction = elem.firstChild.nodeValue
    metadata["sensing_orbit_direction"] = str(direction)

    # sensing_time & sensing_date
    for elem in domfile.getElementsByTagName("safe:startTime"):
        start_time = elem.firstChild.nodeValue
    metadata["sensing_time"] = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%f")
    metadata["sensing_date"] = datetime.strptime(
        start_time.split("T")[0], "%Y-%m-%d"
    ).date()

    # instrument_mode
    for elem in domfile.getElementsByTagName("s1sarl1:mode"):
        instrument_mode = elem.firstChild.nodeValue
    metadata["instrument_mode"] = instrument_mode

    # product_type
    for elem in domfile.getElementsByTagName("s1sarl1:productType"):
        product_type = elem.firstChild.nodeValue
    metadata["product_type"] = product_type

    # product_class
    for elem in domfile.getElementsByTagName("s1sarl1:productClass"):
        product_class = elem.firstChild.nodeValue
    metadata["product_class"] = product_class

    # processing_software_name & version
    for elem in domfile.getElementsByTagName("safe:software"):
        processing_software_name = elem.getAttributeNode("name").nodeValue
        processing_software_version = elem.getAttributeNode("version").nodeValue
    metadata["processing_software_name"] = processing_software_name
    metadata["processing_software_version"] = processing_software_version

    # mission_data_take_id
    for elem in domfile.getElementsByTagName("s1sarl1:missionDataTakeID"):
        mission_data_take_id = elem.firstChild.nodeValue
    metadata["mission_data_take_id"] = int(mission_data_take_id)

    # scene footprint
    metadata["geom"] = extract_s1_footprint(in_dir=in_dir)

    # add storage information
    metadata["storage_device_ip"] = ""
    metadata["storage_device_ip_alias"] = ""
    metadata["storage_share"] = ""

    return metadata


def extract_s1_footprint(in_dir: Path, use_gml: Optional[bool] = True) -> str:
    """
    Extract the Footprint of the S1 scene from the metadata.safe document

    :param in_dir:
        Filepath to the S1 raw data .SAFE folder
    :param use_gml:
        Should the GML coordinates (from the manifest.safe) be used, or the KML coordinates (from
        the ./preview/map-overlay.kml)
    :returns:
        Well-known-text (WKT) of the S1 mapper' footprint in geographic coordinates
        (WGS84, EPSG:4326).
    """
    in_file = in_dir.joinpath("manifest.safe").as_posix()
    # parse Document Object Model (DOM) file from xml
    domfile = minidom.parse(in_file)

    if use_gml:
        # get gml coordinates from manifest.safe file
        for elem in domfile.getElementsByTagName("gml:coordinates"):
            gml_coords = elem.firstChild.nodeValue

        # descrption of gml coords from the S1 product specification document states:
        # "lon,lat of near and far range at start and stop time of the image"
        gml_list = gml_coords.split(" ")
        coord_tuples = [tuple(x.split(",") for x in gml_list)]
        coord_tuples = np.float32(coord_tuples[0])

        # These coords are NOT in lon/lat, but rather in lat/long -> invert coordinates
        invert_coords = []
        for x in coord_tuples:
            invert_coords.append(tuple([x[1], x[0]]))
        invert_coords = np.float32(invert_coords)
        invert_poly = Polygon(LinearRing(invert_coords))
        wkt = invert_poly.wkt

    else:
        # read from KML file
        kml_file = in_dir.joinpath("preview").joinpath("map-overlay.kml").as_posix()
        dom_kml = minidom.parse(kml_file)
        for elem in dom_kml.getElementsByTagName("coordinates"):
            kml_coords = elem.firstChild.nodeValue
        kml_coords = kml_coords.split(" ")
        kml_coords = [tuple(x.split(",") for x in kml_coords)]
        kml_coords = np.float32(kml_coords[0])
        kml_poly = Polygon(LinearRing(kml_coords))
        wkt = kml_poly.wkt

    out_wkt = f"SRID=4326;"
    out_wkt += wkt

    return out_wkt


def loop_s1_archive(
    in_dir: Path,
    get_newest_datasets: Optional[bool] = False,
    last_execution_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    wrapper function to loop over an entire archive (i.e., collection) of
    Sentinel-2 mapper in either L1C or L2A processing level or a mixture
    thereof.

    The function returns a pandas dataframe for all found entries in the
    archive (i.e., directory). Each row in the dataframe denotes one scene.

    :param in_dir:
        directory containing the Sentinel-2 data (L1C and/or L2A
        processing level). Sentinel-2 mapper are assumed to follow ESA's
        .SAFE naming convention and structure
    :param extract_datastrip:
        If True reads also metadata from the datastrip xml file
        (MTD_DS.xml)
    :param get_newest_datasets:
        if set to True only datasets newer than a user-defined time stamp
        will be considered for ingestion into the database. This is particularly
        useful for updating the database after new mapper have been downloaded
        or processed.
    :param last_execution_date:
        if get_newest_datasets is True this variable needs to be set. All
        datasets younger than that date will be considered for ingestion
        into the database.
    :return:
        dataframe with metadata of all mapper handled by the function
        call
    """

    # check inputs if only latest datasets shall be considered
    if get_newest_datasets:
        if last_execution_date is None:
            raise InputError(
                "A timestamp must be provided when the only newest datasets shall be considered"
            )

    # search for .SAFE subdirectories identifying the single mapper
    # some data providers, however, do not name their products following the
    # ESA convention (.SAFE is missing)
    s1_scenes = glob.glob(str(in_dir.joinpath("*.SAFE")))
    n_scenes = len(s1_scenes)

    if n_scenes == 0:
        raise DataNotFoundError(f"No .SAFE mapper found in {in_dir}")

    # if only mapper after a specific timestamp shall be considered drop
    # those from the list which are "too old"
    if get_newest_datasets:
        filtered_scenes = []
        # convert date to Unix timestamp
        last_execution = time.mktime(last_execution_date.timetuple())
        for s1_scene in s1_scenes:
            s1_scene_path = Path(s1_scene)
            if s1_scene_path.stat().st_ctime >= last_execution:
                filtered_scenes.append(s1_scene)
        s1_scenes = filtered_scenes
        if len(s1_scenes) == 0:
            raise DataNotFoundError(
                f'No mapper younger than {datetime.strftime(last_execution_date, "%Y-%m-%d")} found'
            )

    # loop over the mapper
    metadata_scenes = []
    error_file = open(in_dir.joinpath("errored_datasets.txt"), "w+")
    for idx, s1_scene in enumerate(s1_scenes):
        logger.info(
            f"Extracting metadata of {os.path.basename(s1_scene)} ({idx+1}/{n_scenes})"
        )
        try:
            mtd_scene = parse_s1_metadata(in_dir=Path(s1_scene))
        except Exception as e:
            error_file.write(Path(s1_scene).name)
            error_file.flush()
            logger.error(f"Extraction of metadata failed {s1_scene}: {e}")
            continue
        metadata_scenes.append(mtd_scene)

    # convert to pandas dataframe and return
    return pd.DataFrame(metadata_scenes)


# if __name__ == '__main__':
#
#     from eodal.metadata.sentinel1.parsing import parse_s1_metadata
#     from eodal.metadata.sentinel1.database.ingestion import meta_df_to_database
#     from pathlib import Path
#
#     years = [x for x in range(2019,2022)]
#     instrument_mode = 'IW'
#     for year in years:
#         in_dir = Path(f'/home/graflu/public/Evaluation/Satellite_data/Sentinel-1/Rawdata/{instrument_mode}/CH/{year}')
#         metadata = loop_s1_archive(in_dir)
#
#         metadata["storage_device_ip"] = "//hest.nas.ethz.ch/green_groups_kp_public"
#         metadata["storage_device_ip_alias"] = "//nas12.ethz.ch/green_groups_kp_public"
#         metadata["storage_share"] = f"Evaluation/Satellite_data/Sentinel-1/Rawdata/{instrument_mode}/CH/{year}"
#
#         meta_df_to_database(metadata)
