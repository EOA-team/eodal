"""
Vector geometry operations.

Copyright (C) 2022/2023 Lukas Valentin Graf

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

import geopandas as gpd
import json
import pandas as pd
import rasterio as rio

from copy import deepcopy
from pathlib import Path
from rasterio.mask import raster_geometry_mask
from shapely.geometry import box, Point, Polygon

from eodal.core.utils.geometry import convert_3D_2D


def box_to_geojson(gdf: gpd.GeoDataFrame | Polygon) -> str:
    """
    Casts the bounding box of a `GeoDataFrame` to GeoJson

    :param gdf:
        Non-empty `GeoDataFrame` or shapely rectangular Polygon
        in geographic coordinates
    :returns:
        `total_bounds` of gpd in GeoJson notation
    """
    # GeoJSON should be in geographic coordinates
    if isinstance(gdf, gpd.GeoDataFrame):
        _gdf = deepcopy(gdf)
        gdf_wgs84 = _gdf.to_crs(epsg=4326)
        bbox = gdf_wgs84.total_bounds
        bbox_poly = box(*bbox)
    elif isinstance(gdf, Polygon) or isinstance(gdf, Point):
        bbox_poly = deepcopy(gdf)
    bbox_json = gpd.GeoSeries([bbox_poly]).to_json()
    return json.loads(bbox_json)["features"][0]["geometry"]


def box_from_transform(
        transform: list[float] | tuple,
        shape: list[int] | tuple[int, int]
) -> Polygon:
    """
    Get a `shapely` box geometry from a transform vector
    and raster shape.

    ..versionadd:: 0.3.0

    :param transform:
        affine-like transform parameters.
    :param shape:
        raster shape (nrows, ncols).
    :returns:
        resulting geometry as `shapely.geometry.box` object.
    """
    # get pixel resolution
    pixres_x = transform[0]
    pixres_y = transform[4]
    # get origin of raster in spatial reference system coordinates
    minx = transform[2]
    maxy = transform[5]
    # get extent of raster in spatial reference system coordinates
    maxx = minx + (pixres_x * shape[1])
    miny = maxy + (pixres_y * shape[0])
    # construct the box geometry
    return box(minx, miny, maxx, maxy)


def prepare_gdf(
        metadata_list: list[dict]
) -> gpd.GeoDataFrame:
    """
    Convert list of metadata dictionaries to a GeoDataFrame.

    ..versionadd:: 0.3.0

    :param metadata_list:
        list of metadata entries as dictionaries.
    :returns:
        resulting GeoDataFrame sorted by sensing time.
    """
    df = pd.DataFrame(metadata_list)
    df.sort_values(by="sensing_time", inplace=True)
    return gpd.GeoDataFrame(df, geometry="geom", crs=df.epsg.unique()[0])


def adopt_vector_features_to_mask(
        band_df: pd.DataFrame,
        vector_features: gpd.GeoDataFrame | gpd.GeoSeries | Path
) -> gpd.GeoDataFrame:
    """
    Adopt the vector features used for clipping and/or masking data
    to the spatial resolution of the band with the coarsest spatial
    resolution. This is necessary to avoid artifacts (namely different
    spatial extents) in the data caused by the spatial subsetting with
    different pixel sizes.

    ..versionadd:: 0.3.0

    :param band_df:
        DataFrame containing the band metadata.
    :param vector_features:
        vector features to be used for masking.
    :returns:
        Updated vector features.
    """
    # get lowest spatial resolution
    lowest_resolution = band_df["band_resolution"].max()
    # get band with lowest spatial resolution
    low_res_band = band_df[band_df["band_resolution"] == lowest_resolution].iloc[0]
    # get vector feature(s) for spatial subsetting
    if isinstance(vector_features, Path):
        vector_features_df = gpd.read_file(vector_features)
    elif isinstance(vector_features, gpd.GeoDataFrame):
        vector_features_df = vector_features.copy()
    elif isinstance(vector_features, gpd.GeoSeries):
        vector_features_df = gpd.GeoDataFrame(geometry=vector_features.copy())
    else:
        raise TypeError(
            "Geometry must be vector file, GeoSeries or GeoDataFrame"
        )

    # drop Nones in geometry column
    none_idx = vector_features_df[
        vector_features_df.geometry == None].index  # noqa: E711
    vector_features_df.drop(index=none_idx, inplace=True)

    with rio.open(low_res_band.band_path, "r") as src:
        # convert to raster CRS
        raster_crs = src.crs
        vector_features_df.to_crs(crs=raster_crs, inplace=True)
        # check if the geometry contains the z (3rd) dimension. If yes
        # convert it to 2d to avoid an error poping up from rasterio
        vector_features_geom = convert_3D_2D(vector_features_df.geometry)
        shape_mask, transform, window = raster_geometry_mask(
            dataset=src,
            shapes=vector_features_geom,
            all_touched=True,
            crop=True,
        )
    # get upper left coordinates rasterio takes for the band
    # with the coarsest spatial resolution
    ulx_low_res, uly_low_res = transform.c, transform.f
    # reconstruct the lower right corner
    llx_low_res = ulx_low_res + window.width * transform.a
    lly_low_res = uly_low_res + window.height * transform.e

    # overwrite original vector features' bounds in the S2 scene
    # geometry of the lowest spatial resolution
    low_res_feature_bounds_s2_grid = box(
        minx=ulx_low_res,
        miny=lly_low_res,
        maxx=llx_low_res,
        maxy=uly_low_res,
    )
    # update bounds and pass them on to the kwargs
    bounds_df = gpd.GeoDataFrame(
        geometry=[low_res_feature_bounds_s2_grid],
    )
    bounds_df.set_crs(crs=raster_crs, inplace=True)
    return bounds_df
