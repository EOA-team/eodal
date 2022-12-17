"""
Utilities to interact with 2d arrays

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

import itertools
import geopandas as gpd
import numpy as np

from numba import njit, prange
from numpy.ma.core import MaskedArray
from typing import Optional, Union

from eodal.utils.exceptions import InputError
from eodal.core.utils.geometry import check_geometry_types


def count_valid(
    in_array: Union[np.array, MaskedArray],
    no_data_value: Optional[Union[int, float]] = 0.0,
) -> int:
    """
    Counts the number of valid (i.e., non no-data) elements in a 2-d
    array. If a masked array is provided, the number of valid elements is
    the number of not-masked array elements.

    :param in_array:
        two-dimensional array to analyze. Can be an ordinary ``numpy.ndarray``
        or a masked array.
    :param no_data_value:
        no data value indicating invalid array elements. Default set to zero.
        Ignored if ``in_array`` is a ``MaskedArray``
    :returns:
        number of invalid array elements.
    """

    if len(in_array.shape) > 2:
        raise InputError(
            f"Expected a two-dimensional array, got {len(in_array.shape)} instead."
        )

    # masked array already has a count method
    if isinstance(in_array, MaskedArray):
        return in_array.count()

    # check if array is np.array or np.ndarray
    return (in_array != no_data_value).sum()


def upsample_array(
    in_array: np.array,
    scaling_factor: int,
) -> np.array:
    """
    takes a 2-dimensional input array (i.e., image matrix) and splits every
    array cell (i.e., pixel) into X smaller ones having all the same value
    as the "super" cell they belong to, where X is the scaling factor (X>=1).
    This way the input image matrix gets a higher spatial resolution without
    changing any of the original pixel values.

    The value of the scaling_factor determines the spatial resolution of the output.
    If scaling_factor = 1 then the input and the output array are the same.
    If scaling_factor = 2 then the output array has a spatial resolution two times
    higher then the input (e.g. from 20 to 10 m), and so on.

    :param array_in:
        2-d array (image matrix)
    :param scaling_factor:
        factor for increasing spatial resolution. Must be greater than/ equal to 1
    :returns:
        upsampled array with pixel values in target spatial resolution
    """

    # check inputs
    if scaling_factor < 1:
        raise ValueError("scaling_factor must be greater/equal 1")

    # define output image matrix array bounds
    shape_out = (in_array.shape[0] * scaling_factor, in_array.shape[1] * scaling_factor)
    out_array = np.zeros(shape_out, dtype=in_array.dtype)

    # increase resolution using itertools by repeating pixel values
    # scaling_factor times
    counter = 0
    for row in range(in_array.shape[0]):
        column = in_array[row, :]
        out_array[counter : counter + scaling_factor, :] = list(
            itertools.chain.from_iterable(
                itertools.repeat(x, scaling_factor) for x in column
            )
        )
        counter += scaling_factor
    return out_array


# @njit(cache=True, parallel=True)
def _fill_array(
    img_arr: np.ndarray,
    vals: np.ndarray,
    x_indices: np.ndarray,
    x_coords: np.ndarray,
    y_indices: np.ndarray,
    y_coords: np.ndarray,
) -> np.ndarray:
    """
    `numba` accelerated back-end for fast rasterization of POINT
    vector features (`GeoDataFrame` attribute column to 2d-array).

    This method used `NEAREST_NEIGHBOR` to fill in pixel values!

    :param img_arr:
        target 2d array to populate with values from `vals`
    :param vals:
        `POINT` like feature values to rasterize
    :param x_indices:
        `POINT` x coordinates calculated from vector features
    :param x_coords:
        output raster x coordinates (from vector features' spatial
        extent)
    :param y_indices:
        `POINT` y coordinates calculated from vector features
    :param y_coords:
        output raster y coordinates (from vector features' spatial
        extent)
    :returns:
        2d-array with rasterized `POINT` features
    """
    _img_arr = img_arr.copy()
    nvals = vals.shape[0]
    for idx in prange(nvals):
        # search for closest array index corresponding to the pixel
        # and assign the value to the raster cell
        try:
            x_index = np.argmin(abs(x_indices - x_coords[idx]))
            y_index = np.argmin(abs(y_indices - y_coords[idx]))
            _img_arr[y_index, x_index] = vals[idx]
        except IndexError:
            continue
    return _img_arr


def array_from_points(
    gdf: gpd.GeoDataFrame,
    band_name_src: str,
    pixres_x: Union[int, float],
    pixres_y: Union[int, float],
    nodata_dst: Optional[Union[int, float]] = 0,
    dtype_src: Optional[str] = "float32",
) -> np.array:
    """
    Converts a `GeoDataFrame` with POINT features into a 2-d `np.ndarray`
    using the full spatial extent of the input features

    NOTE:
        Currently, only nearest neighbor interpolation is supported

    :param gdf:
        `GeoDataFrame` with POINT features to convert to raster
    :param band_name_src:
        name of `GeoDataFrame` column to rasterize
    :param pixres_x:
        spatial resolution of the output raster (in units of the CRS of the
        `gdf` input) in x direction
    :param pixres_y:
        spatial resolution of the output raster (in units of the CRS of the
        `gdf` input) in y direction
    :param nodata_dst:
        no data values to assign to empty cells. Zero by default.
    :param dtype_src:
        data type of the resulting raster array. Per default "float32" is used.
    :returns:
        2-d `numpy.ndarray` with rasterized POINT features
    """
    # check input geometries, must be Point
    gdf = check_geometry_types(
        in_dataset=gdf, allowed_geometry_types=["Point"], remove_empty_geoms=True
    )

    bounds = gdf.total_bounds
    # get upper left X/Y coordinates
    ulx = bounds[0]
    uly = bounds[-1]
    # get lower right X/Y coordinates to span the img matrix
    lrx = bounds[2]
    lry = bounds[1]
    # calculate max rows along x and y axis
    max_x_coord = int(np.ceil(abs((lrx - ulx) / pixres_x))) + 1
    max_y_coord = int(np.ceil(abs((uly - lry) / pixres_y))) + 1
    # create index lists for coordinates
    x_indices = np.arange(ulx, lrx + pixres_x, step=pixres_x)
    y_indices = np.arange(uly, lry + pixres_y, step=pixres_y)

    # un-flatten the DataFrame along the selected columns (e.g. loop over columns)
    img_arr = np.ones(shape=(max_y_coord, max_x_coord), dtype=dtype_src) * nodata_dst
    x_coords = gdf.geometry.x.values
    y_coords = gdf.geometry.y.values
    vals = gdf[band_name_src].values
    rasterized = _fill_array(img_arr, vals, x_indices, x_coords, y_indices, y_coords)
    return rasterized
