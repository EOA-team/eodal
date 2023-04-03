"""
Metadata filtering utilities for Sentinel-2 data

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
from typing import Optional, Tuple


def identify_updated_scenes(
    metadata_df: pd.DataFrame, return_highest_baseline: Optional[bool] = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns those S2 entries in a pandas ``DataFrame`` retrieved from a query in
    eodal's metadata base that originate from the same orbit and data take
    but were processed by different PDGS Processing Baseline number (the 'Nxxxx'
    in the ``product_uri`` entry in the scene metadata or .SAFE name).

    :param metadata_df:
        dataframe from metadata base query in which to search for mapper with
        the same sensing date and data take but different baseline versions
    :param return_highest_baseline:
        if True (default) return those mapper with the highest baseline. Otherwise
        return the baseline most products belong to
    :return:
        Tuple with two entries. The first entries contains a ``DataFrame`` with
        those S2 mapper belonging to either the highest PDGS baseline or the most
        common baseline version. The other "older" mapper are in the second
        tuple item.
    """

    # get a copy of the input to work with
    metadata = metadata_df.copy()

    # check product uri and extract the processing baseline
    metadata["baseline"] = metadata.product_uri.apply(
        lambda x: int(x.split("_")[3][1:4])
    )

    # get either the highest baseline version or the baseline most datasets
    # belong to depending on the user input
    if return_highest_baseline:
        baseline_sel = metadata.baseline.unique().max()
    else:
        baseline_sel = metadata.baseline.mode()

    # return only those data-set belonging to the selected baseline version
    return (
        metadata[metadata.baseline == baseline_sel],
        metadata[metadata.baseline != baseline_sel],
    )
