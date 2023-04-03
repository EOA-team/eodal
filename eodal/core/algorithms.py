"""
Collection of algorithms working with EOdal core objects such as Bands,
RasterCollections, Scenes and SceneCollections.

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

import eodal
import os
import geopandas as gpd
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from rasterio.merge import merge
from rasterio.crs import CRS

from eodal.config import get_settings
from eodal.core.band import Band, GeoInfo
from eodal.core.raster import RasterCollection, SceneProperties

Settings = get_settings()


def _get_crs_and_attribs(
    in_file: Path, **kwargs
) -> Tuple[GeoInfo, List[Dict[str, Any]]]:
    """
    Returns the ``GeoInfo`` from a multi-band raster dataset

    :param in_file:
        raster datasets from which to extract the ``GeoInfo`` and
        attributes
    :param kwargs:
        optional keyword-arguments to pass to
        `~eodal.core.raster.RasterCollection.from_multi_band_raster`
    :returns:
        ``GeoInfo`` and metadata attributes of the raster dataset
    """

    ds = RasterCollection.from_multi_band_raster(fpath_raster=in_file, **kwargs)
    geo_info = ds[ds.band_names[0]].geo_info
    attrs = [ds[x].get_attributes() for x in ds.band_names]
    return geo_info, attrs


def merge_datasets(
    datasets: List[Path],
    out_file: Optional[Path] = None,
    target_crs: Optional[int | CRS] = None,
    vector_features: Optional[Path | gpd.GeoDataFrame] = None,
    scene_properties: Optional[SceneProperties] = None,
    band_options: Optional[Dict[str, Any]] = None,
    sensor: Optional[str] = None,
    **kwargs,
) -> Union[None, RasterCollection]:
    """
    Merges a list of raster datasets using the ``rasterio.merge`` module.

    The function can handle datasets in different coordinate systems by resampling
    the data into a common spatial reference system either provided in the function
    call or infered from the first dataset in the list.

    ATTENTION:
        All datasets must have the same number of bands and data type!

    :param datasets:
        list of datasets (as path-like objects or opened raster datasets)
        to merge into a single raster
    :param out_file:
        name of the resulting raster dataset (optional). If None (default)
        returns a new ``RasterCollection`` instance otherwise writes the data
        to disk as new raster dataset.
    :param target_crs:
        optional target spatial coordinate reference system in which the output
        product shall be generated. Must be passed as integer EPSG code or CRS
        instance.
    :param vector_features:
        optional vector features to clip the merged dataset to (full bounding box).
    :param scene_properties:
        optional scene properties to set to the resulting merged dataset
    :param band_options:
        optional sensor-specific band options to pass to the sensor's
        ``RasterCollection`` constructor
    :param sensor:
        if the data is from a sensor explicitly supported by eodal such as
        Sentinel-2 the raster data is loaded into a sensor-specific collection
    :param kwargs:
        kwargs to pass to ``rasterio.warp.reproject``
    :returns:
        depending on the kwargs passed either `None` (if output is written to file directly)
        or a `RasterCollection` instance if the operation takes place in memory
    """
    # check the CRS and attributes of the datasets first
    crs_list = []
    attrs_list = []
    for dataset in datasets:
        geo_info, attrs = _get_crs_and_attribs(in_file=dataset)
        crs_list.append(geo_info.epsg)
        attrs_list.append(attrs)

    if target_crs is None:
        # use CRS from first dataset
        target_crs = crs_list[0]
    # coordinate systems are not the same -> re-projection of raster datasets
    if len(set(crs_list)) > 1:
        pass
    # all datasets have one coordinate system, check if it is the desired one
    else:
        if target_crs is not None:
            if crs_list[0] != target_crs:
                # re-projection into target CRS required
                pass

    # use rasterio merge to get a new raster dataset
    dst_kwds = {"QUALITY": "100", "REVERSIBLE": "YES"}
    try:
        res = merge(datasets=datasets, dst_path=out_file, dst_kwds=dst_kwds, **kwargs)
        if res is not None:
            out_ds, out_transform = res[0], res[1]
    except Exception as e:
        raise Exception(f"Could not merge datasets: {e}")

    # when out_file was provided the merged data is written to file directly
    if out_file is not None:
        return
    # otherwise, create new RasterCollection instance from merged datasets
    # add scene properties if available
    if sensor is None:
        raster = RasterCollection(scene_properties=scene_properties)
    else:
        raster = eval(
            f"eodal.core.sensors.{sensor.lower()}.{sensor[0].upper() + sensor[1::]}"
            + "(scene_properties=scene_properties)"
        )
    n_bands = out_ds.shape[0]
    # take attributes of the first dataset
    attrs = attrs_list[0]
    geo_info = GeoInfo(
        epsg=target_crs,
        ulx=out_transform.c,
        uly=out_transform.f,
        pixres_x=out_transform.a,
        pixres_y=out_transform.e,
    )
    for idx in range(n_bands):
        band_attrs = attrs[idx]
        nodata = band_attrs.get("nodatavals")
        if isinstance(nodata, tuple):
            nodata = nodata[0]
        is_tiled = band_attrs.get("is_tiled")
        scale = band_attrs.get("scales")
        if isinstance(scale, tuple):
            scale = scale[0]
        offset = band_attrs.get("offsets")
        if isinstance(offset, tuple):
            offset = offset[0]
        unit = band_attrs.get("units")
        if isinstance(unit, tuple):
            unit = unit[0]

        # get band name and alias if provided
        band_name = band_options.get("band_names", f"B{idx+1}")
        if isinstance(band_name, list):
            if len(band_name) == n_bands:
                band_name = band_name[idx]
            else:
                band_name = f"B{idx+1}"
        band_alias = band_options.get("band_aliases", f"B{idx+1}")
        if isinstance(band_alias, list):
            if len(band_alias) == n_bands:
                band_alias = band_alias[idx]
            else:
                band_alias = f"B{idx+1}"

        raster.add_band(
            band_constructor=Band,
            band_name=band_name,
            values=out_ds[idx, :, :],
            geo_info=geo_info,
            is_tiled=is_tiled,
            scale=scale,
            offset=offset,
            band_alias=band_alias,
            unit=unit,
        )

    # clip raster collection if required to vector_features to keep consistency
    # of masks - this ensures that is_masked_array is set to True
    if vector_features is not None:
        raster.clip_bands(inplace=True, clipping_bounds=vector_features)

    # set scene properties
    if scene_properties is not None:
        raster.scene_properties = scene_properties

    return raster
