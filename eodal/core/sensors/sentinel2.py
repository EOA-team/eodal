"""
This module contains the ``Sentinel2`` class that inherits from
eodal's core ``RasterCollection`` class.

The ``Sentinel2`` class enables reading one or more spectral bands from Sentinel-2
data in .SAFE format which is ESA's standard format for distributing Sentinel-2 data.

The class handles data in L1C and L2A processing level.

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

import cv2
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio as rio

from matplotlib.pyplot import Figure
from matplotlib import colors
from numbers import Number
from pathlib import Path
from rasterio.mask import raster_geometry_mask
from shapely.geometry import box
from typing import Any, Dict, Optional, List, Tuple, Union

from eodal.core.band import Band, WavelengthInfo
from eodal.core.raster import RasterCollection, SceneProperties
from eodal.utils.constants.sentinel2 import (
    band_resolution,
    band_widths,
    central_wavelengths,
    ProcessingLevels,
    s2_band_mapping,
    s2_gain_factor,
    SCL_Classes,
)
from eodal.utils.decorators import prepare_point_features
from eodal.utils.exceptions import BandNotFoundError
from eodal.utils.sentinel2 import (
    get_S2_bandfiles_with_res,
    get_S2_platform_from_safe,
    get_S2_processing_level,
    get_S2_acquistion_time_from_safe,
    get_S2_processing_baseline_from_safe,
)
from eodal.core.utils.geometry import convert_3D_2D
from eodal.config import get_settings
from eodal.utils.sentinel2 import _url_to_safe_name

Settings = get_settings()
Settings.USE_STAC = False


class Sentinel2(RasterCollection):
    """
    Class for storing Sentinel-2 band data read from bandstacks or
    .SAFE archives (L1C and L2A level) overwriting methods inherited
    from `~eodal.utils.io.SatDataHandler`.
    """

    @property
    def is_blackfilled(self) -> bool:
        """Checks if the scene is black-filled (nodata only)"""
        # if SCL is available use this layer
        if "SCL" in self.band_names:
            scl_stats = self.get_scl_stats()
            no_data_count = scl_stats[scl_stats.Class_Value.isin([0])][
                "Class_Abs_Count"
            ].sum()
            all_pixels = scl_stats["Class_Abs_Count"].sum()
            return no_data_count == all_pixels
        # otherwise check the reflectance values from the first
        # band in the collection. If all values are zero then
        # the pixels are considered backfilled
        else:
            band_name = self.band_names[0]
            if self[band_name].is_masked_array:
                return (self[band_name].values.data == 0).all()
            elif self[band_name].is_ndarray:
                return (self[band_name].values == 0).all()
            elif self[band_name].is_zarr:
                raise NotImplementedError()

    @staticmethod
    def _get_gain_and_offset(in_dir: Union[str, Path]) -> Tuple[Number, Number]:
        """
        Returns gain and offset factor depending on the PDGS processing baseline

        :param in_dir:
            Sentinel-2 .SAFE archive folder from which to read data
        :returns:
            tuple whose first entry denotes the gain and whose second entry
            denotes the offset value to apply to the image data to scale
            it between 0 and 1.
        """
        # check the PDGS baseline
        baseline = get_S2_processing_baseline_from_safe(dot_safe_name=in_dir)
        # starting with baseline N0400 (400) S2 reflectances have an offset value of -1000, i.e.,
        # the values reported in the .jp2 files must be subtracted by 1000 to obtain the actual
        # reflectance factor values
        s2_offset = 0
        if baseline == 400:
            s2_offset = -1000
        return (s2_gain_factor, s2_offset)

    @staticmethod
    def _get_band_files(
        in_dir: Union[Path, Dict[str, str]], band_selection: List[str], read_scl: bool
    ) -> pd.DataFrame:
        """
        Returns the paths to the single Sentinel-2 bands.

        There are two options:

        * Returns the file-paths to the selected Sentinel-2 bands in a .SAFE archive
          folder and checks the processing level of the data (L1C or L2A).
        * Returns the links to the assets from a STAC query

        :param in_dir:
            Sentinel-2 .SAFE archive folder from which to read data or dictionary
            with assets from a STAC query
        :param band_selection:
            selection of spectral Sentinel-2 bands to read
        :param read_scl:
            if True and the processing level is L2A the scene classification layer
            is read in addition to the spectral bands
        :returns:
            ``DataFrame`` with paths to the jp2 files with the spectral band data
        """
        # check processing level (use B01 for STAC)
        if Settings.USE_STAC:
            processing_level = get_S2_processing_level(
                dot_safe_name=in_dir["B01"]["href"]
            )
        else:
            processing_level = get_S2_processing_level(dot_safe_name=in_dir)

        # define also a local flag of the processing level so this method also works
        # when called from a classmethod
        is_l2a = True
        if processing_level == ProcessingLevels.L1C:
            is_l2a = False

        # check if SCL should e read (L2A)
        if is_l2a and read_scl:
            scl_in_selection = "scl" in band_selection or "SCL" in band_selection
            if not scl_in_selection:
                band_selection.append("SCL")
        if not read_scl:
            if "scl" in band_selection:
                band_selection.remove("scl")
            if "SCL" in band_selection:
                band_selection.remove("SCL")

        # determine native spatial resolution of Sentinel-2 bands
        band_res = band_resolution[processing_level]
        band_selection_spatial_res = [
            x for x in band_res.items() if x[0] in band_selection
        ]

        # search band files depending on processing level and spatial resolution(s)
        band_df_safe = get_S2_bandfiles_with_res(
            in_dir=in_dir, band_selection=band_selection_spatial_res, is_l2a=is_l2a
        )

        return band_df_safe

    def _process_band_selection(
        self,
        in_dir: Path,
        band_selection: Optional[List[str]] = None,
        read_scl: Optional[bool] = True,
    ) -> pd.DataFrame:
        """
        Adopts the selection of Sentinel-2 spectral bands to ensure
        that default bands are read if not specified otherwise.

        :param in_dir:
            path to the .SAFE archive of the S2 scene
        :param band_selection:
            optional selection of Sentinel-2 band names. If None the band
            selection is aligned so that all 10 and 20m bands are read
        :param read_scl:
            if True (defaults) ensures that the scene classification layer
            is read (L2A processing level)
        :returns:
            ``DataFrame`` with file-paths to the spectral bands
        """
        # load 10 and 20 bands by default
        if band_selection is None:
            band_selection = list(s2_band_mapping.keys())
            bands_to_exclude = ["B01", "B09"]
            for band in bands_to_exclude:
                band_selection.remove(band)

        # determine which spatial resolutions are selected and check processing level
        band_df_safe = self._get_band_files(
            in_dir=in_dir, band_selection=band_selection, read_scl=read_scl
        )
        # check if a band in the band_selection was not found
        if band_selection is not None:
            if len(band_selection) != len(band_df_safe.band_name):
                bands_not_found = [
                    x for x in band_selection if x not in list(band_df_safe.band_name)
                ]
                # SCL might be "missing"
                if len(bands_not_found) == 1:
                    if bands_not_found[0] == "SCL":
                        return band_df_safe
                raise BandNotFoundError(
                    f"Couldnot find bands {bands_not_found} " "provided in selection"
                )
        return band_df_safe

    @classmethod
    def from_safe(
        cls,
        in_dir: Union[Path, Dict[str, str]],
        band_selection: Optional[List[str]] = None,
        read_scl: Optional[bool] = True,
        apply_scaling: Optional[bool] = True,
        **kwargs,
    ):
        """
        Loads Sentinel-2 data into a `RasterCollection`.

        There are two options:

        * Read data from a .SAFE archive which is ESA's standard format for
          distributing Sentinel-2 data (L1C and L2A processing levels).
        * Read data from a Asset-List returned from a STAC query

        NOTE:
            If a spatial subset is read (`vector_features` in kwargs) the
            single S2 bands are clipped to the spatial extent of the S2 in the
            band selection with the coarsest (lowest) spatial resolution. This
            way it is ensured that all bands share the same spatial extent
            regardless of their spatial resolution (10, 20, or 60m). This is
            possible because all bands share the same origin (upper left corner).

        :param in_dir:
            file-path to the .SAFE directory containing Sentinel-2 data in
            L1C or L2A processing level or collection of hyper-links in the case
            of STAC
        :param band_selection:
            selection of Sentinel-2 bands to read. Per default, all 10 and
            20m bands are processed. If you wish to read less or more, specify
            the band names accordingly, e.g., ['B02','B03','B04'] to read only the
            VIS bands. If the processing level is L2A the SCL band is **always**
            loaded unless you set ``read_scl`` to False.
        :param read_scl:
            read SCL file if available (default, L2A processing level).
        :param apply_scaling:
            apply Sentinel-2 gain and offset factor to derive reflectance values scaled
            between 0 (negative values are possible from baseline N0400 onwards) and 1
            (default behavior). Because of the reflectance offset of -1000 introduced with
            PDGS baseline N0400 in January 2022 applying the automatized scaling is recommended
            to always obtain physically correct reflectance factor values - at the cost of
            higher storage requirements because scaling converts the data to float32.
        :param kwargs:
            optional key-word arguments to pass to `~eodal.core.band.Band.from_rasterio`
        :returns:
            `Sentinel2` instance with S2 bands loaded
        """
        # load 10 and 20 bands by default
        band_df_safe = cls._process_band_selection(
            cls, in_dir=in_dir, band_selection=band_selection, read_scl=read_scl
        )

        # check the clipping extent of the raster with the lowest (coarsest) spatial
        # resolution and remember it for all other bands with higher spatial resolutions.
        # By doing so, it is ensured that all bands will be clipped to the same spatial
        # extent regardless of their pixel size. This works since all S2 bands share the
        # same coordinate origin.
        # get lowest spatial resolution (maximum pixel size) band
        align_shapes = False
        masking_after_read_required = False

        if kwargs.get("vector_features") is not None:
            lowest_resolution = band_df_safe["band_resolution"].max()
            if band_df_safe["band_resolution"].unique().shape[0] > 1:
                align_shapes = True
                if kwargs.get("vector_features") is not None:
                    low_res_band = band_df_safe[
                        band_df_safe["band_resolution"] == lowest_resolution
                    ].iloc[0]
                    # get vector feature(s) for spatial subsetting
                    vector_features = kwargs.get("vector_features")
                    if isinstance(vector_features, Path):
                        vector_features_df = gpd.read_file(vector_features)
                    elif isinstance(vector_features, gpd.GeoDataFrame):
                        vector_features_df = vector_features.copy()
                    elif isinstance(vector_features, gpd.GeoSeries):
                        vector_features_df = gpd.GeoDataFrame(
                            geometry=vector_features.copy()
                        )
                    else:
                        raise TypeError(
                            "Geometry must be vector file, GeoSeries or GeoDataFrame"
                        )

                    # drop Nones in geometry column
                    none_idx = vector_features_df[
                        vector_features_df.geometry == None
                    ].index
                    vector_features_df.drop(index=none_idx, inplace=True)

                    with rio.open(low_res_band.band_path, "r") as src:
                        # convert to raster CRS
                        raster_crs = src.crs
                        vector_features_df.to_crs(crs=raster_crs, inplace=True)
                        # check if the geometry contains the z (3rd) dimension. If yes
                        # convert it to 2d to avoid an error poping up from rasterio
                        vector_features_geom = convert_3D_2D(
                            vector_features_df.geometry
                        )
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
                    # remember to mask the feature after clipping the data
                    if not kwargs.get("full_bounding_box_only", False):
                        masking_after_read_required = True
                    # update the vector_features entry
                    kwargs.update({"vector_features": bounds_df})

        # determine platform (S2A or S2B)
        try:
            platform = get_S2_platform_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine platform: {e}")
        # set scene properties (platform, sensor, acquisition date)
        try:
            acqui_time = get_S2_acquistion_time_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine acquisition time: {e}")
        try:
            processing_level = get_S2_processing_level(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine processing level: {e}")
        try:
            if isinstance(in_dir, Path):
                product_uri = in_dir.name
            elif Settings.USE_STAC:
                product_uri = _url_to_safe_name(in_dir)
        except Exception as e:
            raise ValueError(f"Could not determine product uri: {e}")

        scene_properties = SceneProperties(
            acquisition_time=acqui_time,
            platform=platform,
            sensor="MSI",
            processing_level=processing_level,
            product_uri=product_uri,
        )

        # set AREA_OR_POINT to Area
        kwargs.update({"area_or_point": "Area"})
        # set nodata to zero (unfortunately the S2 img metadata is incorrect here)
        kwargs.update({"nodata": 0})
        # set correct scale factor (unfortunately not correct in S2 JP2 header but specified in
        # the MTD_MSIL1C and MTD_MSIL2A.xml metadata document)
        gain, offset = cls._get_gain_and_offset(in_dir=in_dir)

        # loop over bands and add them to the collection of bands
        sentinel2 = cls(scene_properties=scene_properties)
        for band_name in list(band_df_safe.band_name):
            # get entry from dataframe with file-path of band
            band_safe = band_df_safe[band_df_safe.band_name == band_name]
            band_fpath = band_safe.band_path.values[0]

            # get color name and set it as alias
            color_name = s2_band_mapping[band_name]
            kwargs.update({"scale": 1})
            kwargs.update({"offset": 0})

            # store wavelength information per spectral band
            if band_name != "SCL":
                central_wvl = central_wavelengths[platform][band_name]
                wavelength_unit = central_wavelengths["unit"]
                band_width = band_widths[platform][band_name]
                wvl_info = WavelengthInfo(
                    central_wavelength=central_wvl,
                    wavelength_unit=wavelength_unit,
                    band_width=band_width,
                )
                kwargs.update({"wavelength_info": wvl_info})
                # do not apply the gain and offset factors from the spectral bands
                # to the SCL file
                kwargs.update({"scale": gain})
                kwargs.update({"offset": offset})

            # read band
            try:
                sentinel2.add_band(
                    Band.from_rasterio,
                    fpath_raster=band_fpath,
                    band_idx=1,
                    band_name_dst=band_name,
                    band_alias=color_name,
                    **kwargs,
                )
            except Exception as e:
                raise Exception(
                    f"Could not add band {band_name} from {in_dir.name}: {e}"
                )
            # apply actual vector features if masking is required
            if masking_after_read_required:
                # nothing to do when the lowest resolution is passed
                if band_safe.band_resolution.values == lowest_resolution:
                    continue
                # otherwise resample the mask of the lowest resolution to the
                # current resolution using nearest neighbor interpolation
                tmp = shape_mask.astype("uint8")
                dim_resampled = (sentinel2[band_name].ncols, sentinel2[band_name].nrows)
                res = cv2.resize(
                    tmp, dim_resampled, interpolation=cv2.INTER_NEAREST_EXACT
                )
                # cast back to boolean
                mask = res.astype("bool")
                sentinel2.mask(mask=mask, bands_to_mask=[band_name], inplace=True)
        # scaling of reflectance values (i.e., do not scale SCL)
        if apply_scaling:
            sel_bands = sentinel2.band_names
            if "SCL" in sel_bands:
                sel_bands.remove("SCL")
            sentinel2.scale(
                inplace=True,
                band_selection=sel_bands,
                pixel_values_to_ignore=[sentinel2[sentinel2.band_names[0]].nodata],
            )
        return sentinel2

    @classmethod
    @prepare_point_features
    def read_pixels_from_safe(
        cls,
        in_dir: Dict[str, Any] | Path,
        vector_features: Union[Path, gpd.GeoDataFrame],
        band_selection: Optional[List[str]] = None,
        read_scl: Optional[bool] = True,
        apply_scaling: Optional[bool] = True,
    ) -> gpd.GeoDataFrame:
        """
        Extracts Sentinel-2 raster values at locations defined by one or many
        vector geometry features read from a vector file (e.g., ESRI shapefile) or
        ``GeoDataFrame``.

        The Sentinel-2 data must be organized in .SAFE archive structure in either
        L1C or L2A processing level. Each selected Sentinel-2 band is returned as
        a column in the resulting ``GeoDataFrame``. Pixels outside of the band
        bounds are ignored and not returned as well as pixels set to blackfill
        (zero reflectance in all spectral bands).

        IMPORTANT:
            This function works for Sentinel-2 data organized in .SAFE format!
            If the Sentinel-2 data has been converted to multi-band tiffs, use
            `~Sentinel2().read_pixels()` instead.

        NOTE:
            A point is dimension-less, therefore, the raster grid cell (pixel) closest
            to the point is returned if the point lies within the raster.
            Therefore, this method works on all Sentinel-2 bands **without** the need
            to do spatial resampling! The underlying ``rasterio.sample`` function always
            snaps to the closest pixel in the current spectral band.

        :param in_dir:
            Sentinel-2 scene in .SAFE structure from which to extract
            pixel values at the provided point locations. Can be either a dictionary
            item returned from STAC or a physical file-path
        :param vector_features:
            vector file (e.g., ESRI shapefile or geojson) or ``GeoDataFrame``
            defining point locations for which to extract pixel values
        :param band_selection:
            list of bands to read. Per default all raster bands available are read.
        :param read_scl:
            read SCL file if available (default, L2A processing level).
        :param apply_scaling:
            apply Sentinel-2 gain and offset factor to derive reflectance values scaled
            between 0 (negative values are possible from baseline N0400 onwards) and 1
            (default behavior). Because of the reflectance offset of -1000 introduced with
            PDGS baseline N0400 in January 2022 applying the automatized scaling is recommended
            to always obtain physically correct reflectance factor values - at the cost of
            higher storage requirements because scaling converts the data to float32.
        :returns:
            ``GeoDataFrame`` containing the extracted raster values. The band values
            are appended as columns to the dataframe. Existing columns of the input
            `in_file_pixels` are preserved.
        """
        # load 10 and 20 bands by default
        band_df_safe = cls._process_band_selection(
            cls, in_dir=in_dir, band_selection=band_selection, read_scl=read_scl
        )
        # get gain and offset values depending on the processing baseline
        gain, offset = cls._get_gain_and_offset(in_dir=in_dir)

        # loop over spectral bands and extract the pixel values
        band_gdfs = []
        for idx, band_name in enumerate(list(band_df_safe.band_name)):
            # get entry from dataframe with file-path of band
            band_safe = band_df_safe[band_df_safe.band_name == band_name]
            band_fpath = Path(band_safe.band_path.values[0])

            # read band pixels
            try:
                gdf_band = cls.read_pixels(
                    vector_features=vector_features,
                    fpath_raster=band_fpath,
                    band_idxs=[1],
                )
                # rename the spectral band (always "B1" by default to its
                # actual name)
                gdf_band = gdf_band.rename(columns={"B1": band_name})

                # remove the geometry column from all GeoDataFrames but the first
                # since geopandas does not support multiple geometry columns
                # (they are the same for each band, anyways)
                if idx > 0:
                    gdf_band.drop("geometry", axis=1, inplace=True)
            except Exception as e:
                raise Exception(
                    f"Could not extract pixels values from {band_name}: {e}"
                )
            # scale values by applying gain and offset factors (recommended),
            # ignore the scl layer
            if band_name != "SCL":
                if apply_scaling:
                    gdf_scaled = gdf_band.copy()
                    gdf_scaled[band_name] = 0.0
                    # use only pixel values were reflectance is != 0
                    gdf_scaled[band_name] = gdf_band[band_name].apply(
                        lambda x, offset=offset, gain=gain: (offset + x) * gain
                        if x != 0
                        else 0
                    )
                    band_gdfs.append(gdf_scaled)
                    continue
            band_gdfs.append(gdf_band)

        # concatenate the single GeoDataFrames with the band data
        gdf = pd.concat(band_gdfs, axis=1)
        # clean the dataframe and remove duplicate column names after merging
        # to avoid (large) redundancies
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]
        # skip all pixels with zero reflectance (either blackfilled or outside of the
        # scene extent); in case of dtype float check for NaNs
        band_names = gdf.columns[gdf.columns.str.startswith("B")]
        if gdf.dtypes[band_names].unique() in ["float32", "float64"]:
            gdf[band_names] = gdf[band_names].replace({0.0, np.nan})
            gdf.dropna(axis=0, inplace=True)
        elif gdf.dtypes[band_names].unique() in ["int16", "int32", "int64"]:
            gdf = gdf.loc[~(gdf[band_df_safe.band_name] == 0).all(axis=1)]

        return gdf

    def plot_scl(self, colormap: Optional[str] = "") -> Figure:
        """
        Wrapper around `plot_band` method to plot the Scene Classification
        Layer available from the L2A processing level. Raises an error if
        the band is not available

        :param colormap:
            optional matplotlib named colormap to use for visualization. If
            not provided uses a custom color map that tries to reproduce the
            standard SCL colors provided by ESA.
        :return:
            matplotlib figure object with the SCL band data
            plotted as map
        """
        # check if SCL is a masked array. If so, fill masked values with no-data
        # class (for plotting we need to manipulate the data directly),
        #  therefore we work on a copy of SCL
        scl = self["SCL"].copy()
        if scl.is_masked_array:
            new_values = scl.values.filled(
                [k for k, v in SCL_Classes.values().items() if v == "no_data"]
            )
            object.__setattr__(scl, "values", new_values)

        # make a color map of fixed colors
        if colormap == "":
            # get only those colors required (classes in the layer)
            # FIXME: plotting cannot really handle when values are missing in between, e.g., [0,2,3,4]
            scl_colors = SCL_Classes.colors()
            scl_dict = SCL_Classes.values()
            scl_classes = list(np.unique(scl.values))
            selected_colors = [
                x for idx, x in enumerate(scl_colors) if idx in scl_classes
            ]
            scl_cmap = colors.ListedColormap(selected_colors)
            scl_ticks = [x[1] for x in scl_dict.items() if x[0] in scl_classes]
        try:
            return scl.plot(
                colormap=colormap,
                discrete_values=True,
                user_defined_colors=scl_cmap,
                user_defined_ticks=scl_ticks,
            )
        except Exception as e:
            raise BandNotFoundError(f"Could not plot SCL: {e}")

    def mask_clouds_and_shadows(
        self,
        bands_to_mask: Optional[List[str]] = None,
        cloud_classes: Optional[List[int]] = [1, 2, 3, 7, 8, 9, 10, 11],
        mask_band: Optional[str] = "SCL",
        **kwargs,
    ) -> Sentinel2:
        """
        A Wrapper around the inherited ``mask`` method to mask clouds,
        shadows, water and snow based on (by default) the SCL band.
        Works therefore on L2A data, only.

        NOTE:
            Since the `mask_band` can be set to *any* `Band` it is also
            possible to use a different cloud/shadow etc. mask, e.g., from
            a custom classifier.

        NOTE:
            You might also use the mask function from `eodal.core.raster.RasterCollection`
            directly.

        :param bands_to_mask:
            list of bands on which to apply the SCL mask. If not specified all bands
            are masked.
        :param cloud_classes:
            list of SCL values to be considered as clouds/shadows and snow.
            By default, all three cloud classes and cloud shadows are considered
            plus snow.
        :param kwargs:
            optional kwargs to pass to `~eodal.core.raster.RasterCollection.mask`
        :returns:
            depending on `inplace` (passed in the kwargs) a new `Sentinel2` instance
            or None
        """
        if bands_to_mask is None:
            bands_to_mask = self.band_names
        # the mask band should never be masked as otherwise the SCL functions
        # might not work as expected
        if mask_band in bands_to_mask:
            bands_to_mask.remove("SCL")
        try:
            return self.mask(
                mask=mask_band,
                mask_values=cloud_classes,
                bands_to_mask=bands_to_mask,
                **kwargs,
            )
        except Exception as e:
            raise Exception(f"Could not apply cloud mask: {e}")

    def get_scl_stats(self) -> pd.DataFrame:
        """
        Returns a ``DataFrame`` with the number of pixel for each
        class of the scene classification layer. Works for data in
        L2A processing level, only.

        :returns:
            ``DataFrame`` with pixel count of SCL classes available
            in the currently loaded Sentinel-2 scene. Masked pixels
            are ignored and also not used for calculating the relative
            class occurences.
        """
        # check if SCL is available
        if not "scl" in self.band_names and not "SCL" in self.band_names:
            raise BandNotFoundError(
                "Could not find scene classification layer. Is scene L2A?"
            )

        try:
            scl = self.get_band("SCL")
        except BandNotFoundError:
            scl = self.get_band("scl")
        # if the scl array is a masked array consider only those pixels
        # not masked out
        if scl.is_masked_array:
            scl_values = scl.values.compressed()
        else:
            scl_values = scl.values

        # overall number of pixels; masked pixels are not considered
        n_pixels = scl_values.size

        # count occurence of SCL classes
        scl_classes, class_counts = np.unique(scl_values, return_counts=True)
        class_occurences = dict(zip(scl_classes, class_counts))

        # get SCL class name (in addition to the integer code in the data)
        scl_class_mapping = SCL_Classes.values()
        scl_stats_list = []
        for class_occurence in class_occurences.items():
            # unpack tuple
            class_code, class_count = class_occurence

            scl_stats_dict = {}
            scl_stats_dict["Class_Value"] = class_code
            scl_stats_dict["Class_Name"] = scl_class_mapping[class_code]
            scl_stats_dict["Class_Abs_Count"] = class_count
            # calculate percentage of the class count to overall number of pixels in %
            scl_stats_dict["Class_Rel_Count"] = class_count / n_pixels * 100

            scl_stats_list.append(scl_stats_dict)

        # convert to DataFrame
        scl_stats_df = pd.DataFrame(scl_stats_list)

        # append also those SCL classes not found in the scene so that always
        # all SCL classes are returned (this makes handling the DataFrame easier)
        # there are 12 SCL classes, so if the DataFrame has less rows append the
        # missing classes
        if scl_stats_df.shape[0] < len(scl_class_mapping):
            for scl_class in scl_class_mapping:
                if scl_class not in scl_stats_df.Class_Value.values:
                    scl_stats_dict = {}
                    scl_stats_dict["Class_Value"] = int(scl_class)
                    scl_stats_dict["Class_Name"] = scl_class_mapping[scl_class]
                    scl_stats_dict["Class_Abs_Count"] = 0
                    scl_stats_dict["Class_Rel_Count"] = 0

                    scl_stats_df = pd.concat(
                        [
                            scl_stats_df,
                            pd.DataFrame(
                                scl_stats_dict, index=[scl_stats_df.index.max() + 1]
                            ),
                        ]
                    )

        return scl_stats_df

    def get_cloudy_pixel_percentage(
        self,
        cloud_classes: Optional[List[int]] = [2, 3, 7, 8, 9, 10, 11],
    ) -> float:
        """
        Calculates the cloudy pixel percentage [0-100] for the current AOI
        (L2A processing level, only) considering all SCL classes that are
        not NoData.

        :param cloud_classes:
            list of SCL values to be considered as clouds. By default,
            all three cloud classes and cloud shadows are considered.
        :param check_for_snow:
            if True (default) also counts snowy pixels as clouds.
        :returns:
            cloudy pixel percentage in the AOI [0-100%] related to the
            overall number of valid pixels (SCL != no_data)
        """

        # get SCL statistics
        scl_stats_df = self.get_scl_stats()

        # sum up pixels labeled as clouds or cloud shadows
        num_cloudy_pixels = scl_stats_df[scl_stats_df.Class_Value.isin(cloud_classes)][
            "Class_Abs_Count"
        ].sum()
        # check for nodata (e.g., due to blackfill)
        nodata_pixels = scl_stats_df[scl_stats_df.Class_Value.isin([0])][
            "Class_Abs_Count"
        ].sum()

        # and relate it to the overall number of pixels
        all_pixels = scl_stats_df["Class_Abs_Count"].sum()
        cloudy_pixel_percentage = num_cloudy_pixels / (all_pixels - nodata_pixels) * 100
        return cloudy_pixel_percentage


if __name__ == "__main__":
    in_dir = Path(
        "/mnt/ides/Lukas/03_Debug/Sentinel2/S2A_MSIL2A_20171213T102431_N0206_R065_T32TMT_20171213T140708.SAFE"
    )
    vector_features = Path(
        "/mnt/ides/Lukas/02_Research/PhenomEn/01_Data/01_ReferenceData/Strickhof/WW_2022/Bramenwies.shp"
    )
    full_bounding_box_only = True
    s2 = Sentinel2.from_safe(
        in_dir=in_dir,
        vector_features=vector_features,
        full_bounding_box_only=full_bounding_box_only,
    )
    resampled = s2.resample(target_resolution=10)
    assert resampled.is_bandstack(), "raster extents still differ"
    assert (
        not s2.is_bandstack()
    ), "original data must still differ in spatial resolution"

    fpath_raster = in_dir.parent.joinpath("test_10m_full_bbox.jp2")
    resampled.to_rasterio(fpath_raster, band_selection=["B03", "B12"])

    full_bounding_box_only = False
    s2 = Sentinel2.from_safe(
        in_dir=in_dir,
        vector_features=vector_features,
        full_bounding_box_only=full_bounding_box_only,
    )
    resampled = s2.resample(target_resolution=10)
    assert resampled.is_bandstack(), "raster extents still differ"
    fpath_raster = in_dir.parent.joinpath("test_10m_mask.jp2")
    resampled.to_rasterio(fpath_raster, band_selection=["B03", "B12"])
