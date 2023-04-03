"""
This module contains functions to extract relevant scene-specific
Planet-Scope metadata supporting L1C and L2A (sen2core-derived) processing levels

Copyright (C) 2022 Samuel Wildhaber and Lukas Valentin Graf

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

import geojson
import json

from pathlib import Path
from shapely.geometry import shape
from typing import Any, Dict
from xml.dom import minidom


def _parse_metadata_json(in_file: Path) -> Dict[str, Any]:
    """
    Parses the metadata file (*.json) delivered with the Planet-Scope
    mapper

    :param in_file:
        PlanetScope metadata file-path (*.json)
    :returns:
        parsed metadata
    """
    # open the file and parse its properties
    with open(in_file, "r") as src:
        meta = json.load(src)

    # get the required metadata entries
    props = meta["properties"]
    props["scene_id"] = meta["id"]
    props["sensing_time"] = props["acquired"]
    # remove not-required entries
    del props["acquired"]
    del props["published"]
    del props["updated"]
    del props["publishing_stage"]

    # get geometry and convert it into a WKT
    geom = meta["geometry"]
    geom = json.dumps(geom)
    # Convert to geojson.geometry.Polygon
    geom = geojson.loads(geom)
    geom_s = shape(geom)
    props["geom"] = "SRID=4326;" + geom_s.wkt

    # storage location and path handling
    storage_path = in_file.parent.as_posix()
    props["storage_share"] = storage_path
    props["path_type"] = "Posix"
    props["storage_device_ip"] = ""

    return props


def _parse_metadata_xml(in_file: Path) -> Dict[str, Any]:
    """
    Parses the metadata file (*.xml) delivered with the Planet-Scope
    mapper to extract the EPSG code of the scene and the orbit directions

    :param in_file:
        PlanetScope metadata file-path (*.xml)
    :returns:
        parsed metadata
    """
    # parse the xml file into a minidom object
    xmldoc = minidom.parse(str(in_file))
    metadata = {}
    metadata["epsg"] = xmldoc.getElementsByTagName("ps:epsgCode")[
        0
    ].firstChild.nodeValue
    metadata["nrows"] = xmldoc.getElementsByTagName("ps:numRows")[
        0
    ].firstChild.nodeValue
    metadata["ncols"] = xmldoc.getElementsByTagName("ps:numColumns")[
        0
    ].firstChild.nodeValue
    metadata["orbit_direction"] = xmldoc.getElementsByTagName("eop:orbitDirection")[
        0
    ].firstChild.nodeValue
    return metadata


def parse_metadata(in_dir: Path) -> Dict[str, Any]:
    """
    Parses the metadata files (*.json and *.xml) delivered with the Planet-Scope
    mapper and returns the data in a format ready for DB insert

    :param in_dir:
        PS scene directory where metadata and image files are located
    :returns:
        parsed metadata
    """
    # find the json metadata file
    in_file_json = next(in_dir.glob("*.json"))
    json_metadata = _parse_metadata_json(in_file=in_file_json)
    # find the xml metadata file
    in_file_xml = next(in_dir.glob("*.xml"))
    json_metadata.update(_parse_metadata_xml(in_file=in_file_xml))

    return json_metadata


if __name__ == "__main__":
    in_dir = Path("/mnt/ides/Lukas/software/eodal/data/20220414_101133_47_227b")
    metadata = parse_metadata(in_dir)
