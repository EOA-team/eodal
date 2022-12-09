"""
Some auxiliary functions for spatial resampling of raster data

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

import pandas as pd


def identify_split_scenes(
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns entries in a pandas ``DataFrame`` retrieved from a query in eodal's
    metadata base that have the same sensing date. This could indicate, e.g.,
    that mapper have been split because of data take changes which sometimes cause
    Sentinel-2 mapper to be split into two separate .SAFE archives, each of them
    with a large amount of blackfill.

    :param metadata_df:
        dataframe from metadata base query in which to search for mapper with
        the same sensing_date
    :return:
        mapper with the same sensing date (might also be empty)
    """
    return metadata_df[metadata_df.sensing_date.duplicated(keep=False)]
