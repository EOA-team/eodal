"""
Vector geometry operations.

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

import geopandas as gpd
import json

from copy import deepcopy
from shapely.geometry import box, Point, Polygon


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
        gdf_wgs84 = gdf.to_crs(epsg=4326)
        bbox = gdf_wgs84.total_bounds
        bbox_poly = box(*bbox)
    elif isinstance(gdf, Polygon) or isinstance(gdf, Point):
        bbox_poly = deepcopy(gdf)
    bbox_json = gpd.GeoSeries([bbox_poly]).to_json()
    return json.loads(bbox_json)["features"][0]["geometry"]
