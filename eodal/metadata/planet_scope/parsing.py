'''
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
'''

import geojson
import json

from pathlib import Path
from shapely.geometry import shape
from typing import Any, Dict

def parse_metadata(in_file: Path) -> Dict[str, Any]:
    """
    Parses the metadata file (*.json) delivered with the Planet-Scope
    scenes

    :param in_file:
        PlanetScope metadata file-path
    :returns:
        parsed metadata
    """
    # open the file and parse its properties
    with open(in_file, 'r') as src:
        meta = json.load(src)

    # get the required metadata entries
    props = meta['properties']
    props['scene_id'] = meta['id']
    props['sensing_time'] = props['acquired']
    # remove not-required entries
    del props['acquired']
    del props['published']
    del props['updated']
    del props['publishing_stage']

    # get geometry and convert it into a WKT
    geom = meta['geometry']
    geom = json.dumps(geom)
    # Convert to geojson.geometry.Polygon
    geom = geojson.loads(geom)
    geom_s = shape(geom)
    props['geom'] = "SRID=4326;" + geom_s.wkt

    # storage location and path handling
    storage_path = in_file.parent.as_posix()
    props['storage_share'] = storage_path
    props['path_type'] = 'Posix'
    props['storage_device_ip'] = ''

    return props
