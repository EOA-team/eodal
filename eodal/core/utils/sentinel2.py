"""
Helper functions to read Sentinel-2 TCI (RGB quicklook) and Scene Classification Layer
(SCL) file from a .SAFE dataset.

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

from pathlib import Path
from typing import Optional

from eodal.core.raster import RasterCollection
from eodal.core.sensors import Sentinel2
from eodal.utils.sentinel2 import get_S2_tci
from eodal.utils.sentinel2 import get_S2_processing_level
from eodal.utils.constants.sentinel2 import ProcessingLevels


def read_s2_sclfile(in_dir: Path, in_file_aoi: Optional[Path] = None) -> Sentinel2:
    """
    Reads the Sentinel-2 scene classification layer (SCL) file from
    a dataset in .SAFE format.

    ATTENTION:
        The SCL file is available in Level-2 processing level, only

    :param in_dir:
        .SAFE Sentinel-2 archive in Level-2A
    :param in_file_aoi:
        optional vector geometry file defining an area of interest (AOI).
        If not provided, the entire spatial extent of the scene is read
    :return:
        ``RasterCollection`` with SCL band data
    """
    # read SCL file and return
    scl = Sentinel2().from_safe(
        in_dir=in_dir, vector_features=in_file_aoi, band_selection=["SCL"]
    )
    return scl


def read_s2_tcifile(in_dir: Path, in_file_aoi: Optional[Path] = None) -> Sentinel2:
    """
    Reads the Sentinel-2 RGB quicklook file from a data set in
    .SAFE format (processing levels L1C and L2A)

    :param in_dir:
        path to .SAFE Sentinel-2 archive
    :param in_file_aoi:
        optional vector geometry file defining an area of interest (AOI).
        If not provided, the entire spatial extent of the scene is read
    :returns:
        ``RasterCollection`` with quicklook band data
    """

    # determine processing level first
    processing_level = get_S2_processing_level(dot_safe_name=in_dir)

    is_l2a = False
    if processing_level == ProcessingLevels.L2A:
        is_l2a = True

    try:
        tci_file = get_S2_tci(in_dir=in_dir, is_L2A=is_l2a)
    except Exception as e:
        raise Exception from e

    try:
        tci = RasterCollection.from_multi_band_raster(
            fpath_raster=tci_file,
            band_idxs=[1, 2, 3],
            band_aliases=["red", "green", "blue"],
            vector_features=in_file_aoi,
        )
    except Exception as e:
        raise Exception from e

    return tci
