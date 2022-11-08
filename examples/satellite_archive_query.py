"""
sample script showing how to perform a simple metadata query to identify the
number of available scenes for a Sentinel-2 tile below a user-defined cloud
cover threshold on data already downloaded and ingested into the metadata base
(offline mode)

For calling the Copernicus archive (and optionally downloading data) refer
to the script './copernicus_archive_query.py'

The called function also plots the cloud cover over time.

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

import os
from datetime import datetime
from pathlib import Path
from eodal.operational.cli import cli_s2_scene_selection
from eodal.utils.constants import ProcessingLevels

# user inputs
tile = 'T32TLT'
processing_level = ProcessingLevels.L2A
out_dir = Path('/mnt/ides/Lukas/03_Debug')
date_start = '2021-10-01'
date_end = '2022-05-18'
cc_threshold = 80.

# date range
date_start = datetime.strptime(date_start, '%Y-%m-%d')
date_end = datetime.strptime(date_end, '%Y-%m-%d')

# execute scene selection
cli_s2_scene_selection(
    tile=tile,
    processing_level=processing_level,
    cloud_cover_threshold=cc_threshold,
    date_start=date_start,
    date_end=date_end,
    out_dir=Path(out_dir)
)
