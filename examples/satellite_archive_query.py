"""
sample script showing how to perform a simple metadata query to identify the
number of available mapper for a Sentinel-2 tile below a user-defined cloud
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

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from datetime import date, datetime
from pathlib import Path
from eodal.operational.cli import cli_s2_scene_selection
from eodal.utils.constants import ProcessingLevels

# settings for plotting
plt.style.use('seaborn-darkgrid')
matplotlib.rc('ytick', labelsize=16)
matplotlib.rc('xtick', labelsize=16)
matplotlib.rc('font', size=16)

# user inputs
tile = 'T32TLT'
processing_level = ProcessingLevels.L2A
out_dir = Path(f'../data')
date_start = '2019-01-01'
date_end = '2020-12-31'
cc_threshold = 100.

# date range
date_start = datetime.strptime(date_start, '%Y-%m-%d')
date_end = datetime.strptime(date_end, '%Y-%m-%d')

# execute scene selection (plots cloud cover over time)
metadata = cli_s2_scene_selection(
    tile=tile,
    processing_level=processing_level,
    cloud_cover_threshold=cc_threshold,
    date_start=date_start,
    date_end=date_end,
    out_dir=Path(out_dir)
)

# plot cloud cover by month
date_start = date(2017,1,1)
date_end = date(2021,12,31)

metadata = cli_s2_scene_selection(
    tile=tile,
    processing_level=processing_level,
    cloud_cover_threshold=cc_threshold,
    date_start=date_start,
    date_end=date_end,
    out_dir=Path(out_dir)
)

# group by month and plot the average cloud cover
metadata_monthly = metadata['cloudy_pixel_percentage'].groupby(
    by=pd.to_datetime(metadata.sensing_date).dt.month).agg('median')
metadata_monthly = metadata_monthly.reset_index()
months = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep',
          10: 'Oct', 11: 'Nov', 12: 'Dec'}
metadata_monthly.sensing_date = metadata_monthly.sensing_date.map(months)

f, ax = plt.subplots(figsize=(8,6))
ax.plot(metadata_monthly.sensing_date, metadata_monthly.cloudy_pixel_percentage,
        marker='o', label='Median')
ax.set_xlabel('Month', fontsize=16)
ax.set_ylabel('Cloudy Pixel Percentage [%]', fontsize=16)
ax.set_title(f'Sentinel-2 Tile {tile[1::]} ({date_start} - {date_end})\nNumber of Scenes: {metadata.shape[0]}',
             size=18)
ax.set_ylim(0,100)
ax.set_xlim(-1,12)
ax.legend(fontsize=16)
f.savefig(out_dir.joinpath(f'monthly_cloudy_pixel_percentage_{date_start}-{date_end}.png'), bbox_inches='tight')

