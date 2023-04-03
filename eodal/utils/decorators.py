"""
Function and method decorators used to validate passed arguments.

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

from functools import wraps
from pathlib import Path
from rasterio.coords import BoundingBox

from eodal.config import get_settings
from eodal.core.utils.geometry import multi_to_single_points
from eodal.utils.exceptions import UnknownProcessingLevel, BandNotFoundError
from eodal.utils.geometry import box_to_geojson

Settings = get_settings()


def prepare_bbox(f):
    """prepares a bounding box from 1:N vector features for STAC queries"""

    @wraps(f)
    def wrapper(**kwargs):
        # a bounding box (vector features) is required
        vector_features = kwargs.get("bounding_box", None)
        if vector_features is None:
            raise ValueError("A bounding box must be specified")
        if isinstance(vector_features, Path):
            vector_features = gpd.read_file(vector_features)
        # construct the bounding box from vector features
        # the bbox must be provided as a polygon in geographic coordinates
        # and provide bounds as geojson (required by STAC)
        bbox = box_to_geojson(gdf=vector_features)
        kwargs.update({"bounding_box": bbox})
        return f(**kwargs)

    return wrapper


def prepare_point_features(f):
    """
    casts MultiPoint geometries to single parts before calling pixel extraction methods
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        vector_features = kwargs.get("vector_features")
        if vector_features is None:
            vector_features = args[2]
        # cast to single point geometries
        try:
            vector_features_updated = multi_to_single_points(vector_features)
        except Exception as e:
            print(e)
        if "vector_features" in kwargs.keys():
            kwargs.update({"vector_features": vector_features_updated})
        else:
            arg_list = list(args)
            arg_list[2] = vector_features_updated
            args = tuple(arg_list)
        return f(*args, **kwargs)

    return wrapper


def check_processing_level(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        processing_level = ""
        if len(args) > 0:
            processing_level = args[1]
        if kwargs != {}:
            processing_level = kwargs.get("processing_level", processing_level)

        if not processing_level in Settings.PROCESSING_LEVELS:
            raise UnknownProcessingLevel(
                f"{processing_level} is not part of {Settings.PROCESSING_LEVELS}"
            )
        return f(*args, **kwargs)

    return wrapper


def check_band_names(f):
    """checks if passed band name(s) are available"""

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        band_names = None
        if len(args) == 0 and len(kwargs) == 0:
            return f(self, *args, **kwargs)

        if len(args) > 0:
            # band name(s) are always provided as first argument
            band_names = args[0]
        if kwargs != {} and band_names is None:
            # check for band_name and band_names key word argument
            band_names = kwargs.get("band_name", band_names)
            if band_names is None:
                band_names = kwargs.get("band_selection", band_names)

        # check if band aliases is enabled
        if self.has_band_aliases:
            # check if passed band names are actual band names or their alias
            if isinstance(band_names, str):
                band_name = band_names
                if band_name not in self.band_names:
                    # passed band name is alias
                    if band_name in self.band_aliases:
                        band_idx = self.band_aliases.index(band_name)
                        band_name = self.band_names[band_idx]
                        if len(args) > 0:
                            arg_list = list(args)
                            arg_list[0] = band_name
                            args = tuple(arg_list)
                        if kwargs != {} and "band_name" in kwargs.keys():
                            kwargs.update({"band_name": band_name})
                    else:
                        raise BandNotFoundError(f"{band_names} not found in collection")
            elif isinstance(band_names, list):
                # check if passed band names are aliases
                if set(band_names).issubset(self.band_names):
                    new_band_names = band_names
                else:
                    new_band_names = []
                    for band_name in band_names:
                        try:
                            new_band_names.append(self[band_name].alias)
                        # band name must be in band names if not an alias
                        except Exception:
                            raise BandNotFoundError(
                                f"{band_name} not found in collection"
                            )
                if len(args) > 0:
                    arg_list = list(args)
                    arg_list[0] = new_band_names
                    args = tuple(arg_list)
                if kwargs != {} and "band_selection" in kwargs.keys():
                    kwargs.update({"band_selection": new_band_names})

        # if no band aliasing is enabled the passed name must be in band names
        else:
            if isinstance(band_names, str):
                if not band_names in self.band_names:
                    raise BandNotFoundError(f"{band_names} not found in collection")
            elif isinstance(band_names, list):
                if not set(band_names).issubset(self.band_names):
                    raise BandNotFoundError(f"{band_names} not found in collection")

        return f(self, *args, **kwargs)

    return wrapper


def check_metadata(f):
    """validates if passed image metadata items are valid"""

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        meta_key, meta_values = None, None

        if len(args) > 0:
            meta_key = args[0]
            meta_values = args[1]
        if kwargs != {}:
            if meta_key is None:
                meta_key = kwargs.get("metadata_key", meta_key)
            if meta_values is None:
                meta_values = kwargs.get("metadata_values", meta_values)

        # check different entries
        # image metadata
        if meta_key == "meta":
            meta_keys = [
                "driver",
                "dtype",
                "nodata",
                "width",
                "height",
                "count",
                "crs",
                "transform",
            ]
            if set(list(meta_values.keys())) != set(meta_keys):
                raise Exception("The passed meta-dict is invalid")
        # bounds
        elif meta_key == "bounds":
            if not type(meta_values) == BoundingBox:
                raise Exception("The passed bounds are not valid.")

        return f(self, *args, **kwargs)

    return wrapper
