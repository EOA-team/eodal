"""
Raster utilities to extract raster band attributes

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

import math
import numpy as np
import rasterio as rio

from rasterio import Affine
from typing import Any, Dict, Tuple


def get_raster_attributes(riods: rio.io.DatasetReader) -> Dict[str, Any]:
    """
    extracts immutable raster attributes (not changed by reprojections,
    resampling) and returns them as a dictionary.

    Code taken from
    https://github.com/pydata/xarray/blob/960010b00119367ff6b82e548f2b54ca25c7a59c/xarray/backends/rasterio_.py#L359

    :param riods:
        opened ``rasterio`` data set reader
    :returns:
        dictionary with extracted raster attributes (attrs)
    """

    attrs = {}

    if hasattr(riods, "is_tiled"):
        # Is the TIF tiled? (bool)
        # We cast it to an int for netCDF compatibility
        attrs["is_tiled"] = np.uint8(riods.is_tiled)
    if hasattr(riods, "nodatavals"):
        # The nodata values for the raster bands
        attrs["nodatavals"] = tuple(
            np.nan if nodataval is None else nodataval for nodataval in riods.nodatavals
        )
    if hasattr(riods, "scales"):
        # The scale values for the raster bands
        attrs["scales"] = riods.scales
    if hasattr(riods, "offsets"):
        # The offset values for the raster bands
        attrs["offsets"] = riods.offsets
    if hasattr(riods, "descriptions") and any(riods.descriptions):
        # Descriptions for each dataset band
        attrs["descriptions"] = riods.descriptions
    if hasattr(riods, "units") and any(riods.units):
        # A list of units string for each dataset band
        attrs["units"] = riods.units

    return attrs


def spatial_to_image_coordinates(
    x: float, y: float, affine: Affine, op=math.floor
) -> Tuple[int, int]:
    """
    Convert spatial x and y coordinat to image coordinates (row + column)

    .. versionadded:: 0.1.1

    taken from:
        `rasterstats` package under BSD 3-Clause "New" or "Revised" License
        Copyright (c) 2013 Matthew Perry
        https://github.com/perrygeo/python-rasterstats/blob/d05f0dbda82c7a54fbb99d893af6e3182c225005/src/rasterstats/io.py#L137
    """
    r = int(op((y - affine.f) / affine.e))
    c = int(op((x - affine.c) / affine.a))
    return r, c


def bounds_window(
    bounds: Tuple[float, float, float, float], affine: Affine
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Create a full cover rasterio-style window

    .. versionadded:: 0.1.1

    taken from:
        `rasterstats` package under BSD 3-Clause "New" or "Revised" License
        Copyright (c) 2013 Matthew Perry
        https://github.com/perrygeo/python-rasterstats/blob/d05f0dbda82c7a54fbb99d893af6e3182c225005/src/rasterstats/io.py#L145
    """
    w, s, e, n = bounds
    row_start, col_start = spatial_to_image_coordinates(w, n, affine)
    row_stop, col_stop = spatial_to_image_coordinates(e, s, affine, op=math.ceil)
    return row_start, row_stop, col_start, col_stop
