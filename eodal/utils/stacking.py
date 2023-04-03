"""
Stacking of `pandas.DataFrame` objects.

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

import os
import glob
import pandas as pd
from pathlib import Path
from typing import Optional


def stack_dataframes(
    in_dir: Path,
    search_pattern: str,
    start_date: Optional[int] = None,
    end_date: Optional[int] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    stacks a list of pandas dataframes into a single big one
    to allow for calculating multitemporal statistics and more
    convenient handling of pixels and field polygons

    :param in_dir:
        directory in which to search for CSV files to be read into memory
    :param search_pattern:
        wild-card expression for searching for CSV files with pixel reflectance
        values (e.g., '*10m.csv')
    :param start_date:
        start date in the format YYYYMMDD to use for filtering CSV files. If None
        (Default), all files are stacked
    :param end_date:
        end date in the format YYYYMMDD to use for filtering CSV files. If None
        (Default), all files are stacked
    :param **kwargs:
        keyword arguments to pass to pandas.read_csv()
    """
    # get a list of all CSV files matching the search pattern
    csv_files = glob.glob(str(in_dir.joinpath(search_pattern)))

    # loop over files and read them into dataframes
    all_df = []
    for csv_file in csv_files:
        if start_date is not None and end_date is not None:
            date_file = int(os.path.basename(csv_file)[0:8])
            if date_file < start_date or date_file > end_date:
                continue
        tmp_df = pd.read_csv(csv_file, **kwargs)
        all_df.append(tmp_df)

    # concat the obtained list of dataframes into a single one and return
    return pd.concat(all_df)
