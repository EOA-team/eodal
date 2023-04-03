"""
This module contains the ``Sentinel1`` class that inherits from
eodal's core ``RasterCollection`` class.

The ``Sentinel1`` class enables reading one or more polarizations from Sentinel-1
data in .SAFE format which is ESA's standard format for distributing Sentinel-1 data.

The class handles data in GRD (ground-range detected) and RTC (radiometrically terrain
corrected) processing level.

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
import pandas as pd
import planetary_computer

from pathlib import Path
from typing import Any, Dict, List, Optional

from eodal.config import get_settings
from eodal.core.band import Band
from eodal.core.raster import RasterCollection, SceneProperties
from eodal.utils.decorators import prepare_point_features
from eodal.utils.sentinel1 import (
    get_S1_platform_from_safe,
    get_S1_acquistion_time_from_safe,
    _url_to_safe_name,
    get_s1_imaging_mode_from_safe,
)
from eodal.utils.exceptions import DataNotFoundError

Settings = get_settings()


class Sentinel1(RasterCollection):
    """
    Reading Sentinel-1 Radiometrically Terrain Corrected (RTC) and
    Ground Range Detected (GRD) products
    """

    @staticmethod
    def _get_band_files(
        in_dir: Path | Dict[str, str], polarizations: List[str]
    ) -> pd.DataFrame:
        """
        Get file-paths to Sentinel-1 polarizations

        :param in_dir:
            file-path to the Sentinel-1 RTC SAFE or dictionary with asset
            items returned from STAC query
        :param polarizations:
            selection of polarization to read
        :returns:
            `DataFrame` with found files and links to them
        """
        band_items = []
        for polarization in polarizations:
            if Settings.USE_STAC:
                # get band files from STAC (MS PC)
                href = in_dir[polarization.lower()]["href"]
                # sign href (this works only with a valid API key)
                ref = planetary_computer.sign_url(href)
            else:
                try:
                    ref = next(
                        in_dir.glob(f"measurement/s1*-{polarization.lower()}-*.tiff")
                    )
                except Exception as e:
                    raise DataNotFoundError(
                        f"Could not find data for polarization {polarization} in {in_dir}: {e}"
                    )
            item = {"polarization": polarization, "file_path": ref}
            band_items.append(item)
        return pd.DataFrame(band_items)

    @classmethod
    def from_safe(
        cls,
        in_dir: Path | Dict[str, str],
        polarizations: Optional[List[str]] = ["VV", "VH"],
        **kwargs,
    ):
        """
        Reads a Sentinel-1 RTC (radiometrically terrain corrected) or
        GRD (Ground Range Detected) products

        NOTE
            When using MSPC as STAC provider a valid API key is required

        :param in_dir:
            file-path to the Sentinel-1 RTC SAFE or dictionary with asset
            items returned from STAC query
        :param polarizations:
            selection of polarization to read. 'VV' and 'VH' by default.
        :param kwargs:
            optional key word arguments to pass on to
            `~eodal.core.raster.RasterCollection.from_rasterio`
        """
        # get file-paths
        band_df = cls._get_band_files(in_dir, polarizations)

        # set scene properties (platform, sensor, acquisition date)
        try:
            platform = get_S1_platform_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine platform: {e}")
        try:
            acqui_time = get_S1_acquistion_time_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine acquisition time: {e}")
        try:
            mode = get_s1_imaging_mode_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine imaging mode: {e}")
        try:
            if isinstance(in_dir, Path):
                product_uri = in_dir.name
            elif Settings.USE_STAC:
                product_uri = _url_to_safe_name(in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine product uri: {e}")

        # get a new RasterCollection
        scene_properties = SceneProperties(
            acquisition_time=acqui_time,
            platform=platform,
            sensor="SAR",
            product_uri=product_uri,
            mode=mode,
        )
        sentinel1 = cls(scene_properties=scene_properties)

        # add bands
        for _, band_item in band_df.iterrows():
            sentinel1.add_band(
                band_constructor=Band.from_rasterio,
                fpath_raster=band_item.file_path,
                band_name_dst=band_item.polarization,
                **kwargs,
            )

        return sentinel1

    @classmethod
    @prepare_point_features
    def read_pixels_from_safe(
        cls,
        in_dir: Dict[str, Any] | Path,
        vector_features: Path | gpd.GeoDataFrame,
        polarizations: Optional[List[str]] = ["VV", "VH"],
    ) -> gpd.GeoDataFrame:
        """
        Extracts Sentinel-1 raster values at locations defined by one or many
        vector geometry features read from a vector file (e.g., ESRI shapefile) or
        ``GeoDataFrame``.

        NOTE:
            A point is dimension-less, therefore, the raster grid cell (pixel) closest
            to the point is returned if the point lies within the raster.

        :param in_dir:
            Sentinel-1 scene in .SAFE structure from which to extract pixel values at
            the provided point locations (GRD or RTC).Can be either a dictionary
            item returned from STAC or a physical file-path
        :param vector_features:
            vector file (e.g., ESRI shapefile or geojson) or ``GeoDataFrame``
            defining point locations for which to extract pixel values
        :param polarizations:
            selection of polarization to read. 'VV' and 'VH' by default.
        :returns:
            ``GeoDataFrame`` containing the extracted raster values. The band values
            are appended as columns to the dataframe. Existing columns of the input
            `in_file_pixels` are preserved.
        """
        # get file-paths
        band_df = cls._get_band_files(in_dir, polarizations)
        # read pixel values from bands
        gdf_list = []
        for _, band_item in band_df.iterrows():
            gdf_polarization = cls.read_pixels(
                vector_features=vector_features,
                fpath_raster=band_item.file_path,
                band_idxs=[1],
            )
            gdf_polarization = gdf_polarization.rename(
                columns={"B1": band_item.polarization}
            )
            gdf_list.append(gdf_polarization)

        # concatenate the single GeoDataFrames with the band data
        gdf = pd.concat(gdf_list, axis=1)
        # clean the dataframe and remove duplicate column names after merging
        # to avoid (large) redundancies
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]
        return gdf


if __name__ == "__main__":
    in_dir = Path(
        "/home/graflu/public/Evaluation/Satellite_data/Sentinel-1/Rawdata/IW/CH/2021/S1A_IW_GRDH_1SDV_20210106T053505_20210106T053530_036013_043833_C728.SAFE"
    )
    s1 = Sentinel1.from_safe(in_dir=in_dir, epsg_code=4326)
