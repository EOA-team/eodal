"""
Functions for reprojecting vector and raster data from one spatial
coordinate reference system into another one.

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

import numpy as np
import rasterio as rio
import geopandas as gpd

from collections import namedtuple
from rasterio import Affine
from rasterio.crs import CRS
from shapely.geometry import box, MultiPolygon, Polygon
from pathlib import Path
from typing import NamedTuple, Optional, Tuple, Union
from geopandas import GeoDataFrame

from eodal.core.utils.geometry import read_geometries

UTMZone = namedtuple("Point", "zone hemisphere")


def _infer_utm_zone(shape: Polygon | MultiPolygon) -> NamedTuple:
    """
    Infer the UTM zone from a geometry provided in geographic coordinates.
    The geometry must implement the centroid attribute.

    :param shape:
        geometry in geographic coordinates (WGS84) for which to check
        the corresponding UTM zone
    :returns:
        `NamedTuple` with two-digit UTM `zone` number and `hemisphere`
        (north or south)
    """
    centroid = shape.centroid
    lon = centroid.x
    lat = centroid.y

    if lat > 84 or lat < -80:
        raise Exception("UTM Zones only valid within [-80, 84] latitude")

    zone = int((lon + 180) / 6 + 1)
    hemisphere = "north" if lat > 0 else "south"
    return UTMZone(zone, hemisphere)


def _epsg_from_utm_zone(utmzone: UTMZone) -> int:
    """
    EPSG code from UTM zone number and hemisphere

    :param utmzone:
        `NamedTuple` with two-digit UTM `zone` and `hemisphere`
    :returns:
        integer EPSG code
    """
    epsg_str = "32"
    if utmzone.hemisphere == "north":
        epsg_str += "6"
    elif utmzone.hemisphere == "south":
        epsg_str += "7"
    else:
        raise ValueError("Not a valid hemisphere (allowed: north or south)")
    epsg_str += str(utmzone.zone)
    return int(epsg_str)


def infer_utm_zone(shape: Polygon | MultiPolygon) -> int:
    """
    Returns the EPSG code of the UTM zone a geometry with geographic coordinates
    lies in (i.e., its centroid)

    :param shape:
        geometry in geographic coordinates (WGS84) for which to check
        the corresponding UTM zone
    """
    utmzone = _infer_utm_zone(shape)
    return _epsg_from_utm_zone(utmzone)


def check_aoi_geoms(
    in_dataset: Union[Path, gpd.GeoDataFrame],
    full_bounding_box_only: bool,
    fname_raster: Optional[Path] = None,
    raster_crs: Optional[Union[int, CRS]] = None,
) -> GeoDataFrame:
    """
    Checks the provided vector file. If necessary it reprojects
    the vector data in the reference system of the provided raster
    data. If the full bounding box shall be used (e.g., the hull
    encompassing all provided vector geometries) it only returns
    this geometry (of type Polygon).

    NOTE:
        Does not check for spatial intersects, overlaps, etc.

    :param in_file_aoi:
        vector file (e.g., ESRI shapefile or geojson) defining geometry/ies
        for which to extract raster data.
    :param fname_raster:
        raster file to which to map the vector features. Can be ignored if
        a ``raster_crs`` is available
    :param full_bounding_box_only:
        if set to False, will only extract the data for those geometry/ies
        defined in in_file_aoi. If set to False, returns the data for the
        full extent (hull) of all features (geometries) in in_file_aoi.
    :param raster_crs:
        spatial reference system of the raster as EPSG code or ``CRS`` object.
        Can be ignored if ``fname_sat`` is available.
    :return:
        GeoDataFrame with one up to many vector geometries
    """

    # check for vector features defining AOI
    gdf = read_geometries(in_dataset)

    # check if the spatial reference systems match
    sat_crs = None
    if fname_raster is not None:
        sat_crs = rio.open(fname_raster).crs
    if raster_crs is not None and sat_crs is None:
        sat_crs = raster_crs

    # reproject vector data if necessary
    if gdf.crs != sat_crs:
        gdf.to_crs(sat_crs, inplace=True)

    # if the the entire bounding box shall be extracted
    # we need the hull encompassing all geometries in gdf
    if full_bounding_box_only:
        bbox = box(*gdf.total_bounds)
        gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(bbox))

    return gdf


def reproject_raster_dataset(
    raster: Union[Path, np.ndarray], **kwargs
) -> Tuple[Union[Path, np.ndarray], Affine]:
    """
    Re-projects a raster dataset into another spatial coordinate reference
    system by calling ``rasterio.warp.reproject``.

    :param raster:
        either a file-path to a raster dataset or a numpy array
        containing band data to reproject
    :param kwargs:
        kwargs required by ``rasterio.warp.reproject``. See rasterio's docs
        for more information.
    :return:
        tuple containing the reprojected raster dataset (file-path or array)
        and the ``Affine`` transformation parameters of the reprojected dataset
    """

    try:
        dst, transform = rio.warp.reproject(source=raster, **kwargs)
    except Exception as e:
        raise Exception from e

    return dst, transform
