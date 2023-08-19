"""
This module contains the ``Landsat`` class that inherits from
eodal's core ``RasterCollection`` class.

The ``Landsat`` class enables reading one or more spectral bands from Landsat 5 to 9
science products in L2 processing level.

The class handles data in L1C and L2A processing level.

Copyright (C) 2023 Lukas Valentin Graf

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
import io
import json
import numpy as np
import pandas as pd
import planetary_computer
import requests
import warnings

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree

from eodal.config import get_settings, STAC_Providers
from eodal.core.band import Band
from eodal.core.raster import RasterCollection, SceneProperties
from eodal.utils.geometry import adopt_vector_features_to_mask
from eodal.utils.constants import ProcessingLevels
from eodal.utils.constants.landsat import (
    band_resolution,
    landsat_band_mapping,
    platform_sensor_mapping)
from eodal.utils.types import xml_to_dict_recursive

Settings = get_settings()


class Landsat(RasterCollection):
    """
    Class for working with Landsat science products (Level-2).
    """

    @staticmethod
    def _get_available_bands(
            in_dir: Path | Dict[str, str],
    ) -> list[str]:
        """
        Check the available bands in the input directory and return the
        bands found in a list.

        :param in_dir:
            Path to the directory containing the Landsat data or collection of
            hyper-links in the case of STAC. If a dictionary is passed, we assume
            that all files are stored in the same directory.
        :return:
            List of available bands.
        """
        if isinstance(in_dir, dict):
            available_bands = list(in_dir.keys())
            # remove non-band files
            available_bands = [
                x for x in available_bands if Path(x).suffix
                not in ['.txt', '.xml', '.json']
                and x != 'tilejson'
                and x != 'rendered_preview']
        elif isinstance(in_dir, Path):
            available_bands = [f.stem.split('_')[-1] for f in in_dir.glob("*.TIF")]
        else:
            raise TypeError("in_dir must be a Path or a dictionary.")
        return available_bands

    @staticmethod
    def _check_platform(
            in_dir: Path | Dict[str, str]
    ) -> str:
        """
        Check which Landsat platform (spacecraft) produced the data.
        """
        if isinstance(in_dir, dict):
            # the green band should be always available
            test_band = in_dir['green']['href'].split('/')[-1]
        elif isinstance(in_dir, Path):
            test_band = in_dir.glob("*_B*.TIF")[0]
        # get the platform from the band name
        platform = test_band.split('_')[0]
        return platform

    @staticmethod
    def _get_metadata_json(
            in_dir: Path | Dict[str, str]
    ) -> dict:
        """
        Get the Landsat metadata JSON file from the input directory.
        """
        if isinstance(in_dir, dict):
            metadata_url = planetary_computer.sign_url(in_dir['mtl.json']['href'])
            response_code = requests.get(metadata_url).status_code
            # check for JSON or XML
            if response_code == 200:
                metadata = json.loads(requests.get(metadata_url).content)
            elif response_code == 404:
                metadata_url = planetary_computer.sign_url(in_dir['mtl.xml']['href'])
                metadata_xml_tree = ElementTree.parse(
                    io.BytesIO(requests.get(metadata_url).content))
                metadata_xml_root = metadata_xml_tree.getroot()
                # convert to dictionary
                metadata = xml_to_dict_recursive(metadata_xml_root)
        elif isinstance(in_dir, Path):
            fpath_json = in_dir.joinpath('MTL.json')
            if fpath_json.exists():
                with open(fpath_json, 'r') as src:
                    metadata = json.load(src)
            else:
                fpath_xml = in_dir.joinpath('MTL.xml')
                metadata_xml_tree = ElementTree.parse(fpath_xml)
                metadata_xml_root = metadata_xml_tree.getroot()
                # convert to dictionary
                metadata = xml_to_dict_recursive(metadata_xml_root)
        return metadata

    @staticmethod
    def _product_uri_from_filename(
            in_dir: Path | Dict[str, str]
    ) -> str:
        """
        Get the product URI from the file name.

        :param in_dir:
            Path to the directory containing the Landsat data or collection of
            hyper-links in the case of STAC. If a dictionary is passed, we assume
            that all files are stored in the same directory.
        :return:
            Product URI.
        """
        if isinstance(in_dir, dict):
            # the green band should be always available
            test_band = in_dir['green']['href'].split('/')[-1]
        elif isinstance(in_dir, Path):
            test_band = in_dir.glob("*.TIF")[0]
        # get the product URI from the band name
        product_uri = '_'.join(test_band.split('_')[:-2])
        return product_uri

    @staticmethod
    def _sensing_time_from_filename(
            in_dir: Path | Dict[str, str]
    ) -> datetime:
        """
        Get the sensing time from the file name.

        :param in_dir:
            Path to the directory containing the Landsat data or collection of
            hyper-links in the case of STAC. If a dictionary is passed, we assume
            that all files are stored in the same directory.
        :return:
            Sensing time.
        """
        if isinstance(in_dir, dict):
            # the green band should be always available
            test_band = in_dir['red']['href'].split('/')[-1]
        elif isinstance(in_dir, Path):
            test_band = in_dir.glob("*.TIF")[0]
        # get the sensing time from the metadata file
        metadata = Landsat._get_metadata_json(in_dir)['LANDSAT_METADATA_FILE']

        # unpack dictionaries from lists
        if isinstance(metadata, list):
            metadata_as_dict = {}
            for entry in metadata:
                for k, v in entry.items():
                    metadata_as_dict.update({k: {}})
                    for inner_item in v:
                        metadata_as_dict[k].update(inner_item)
            metadata = metadata_as_dict

        date = metadata['IMAGE_ATTRIBUTES']['DATE_ACQUIRED']
        scene_center_time = metadata['IMAGE_ATTRIBUTES']['SCENE_CENTER_TIME']
        combined = date + ' ' + scene_center_time.split('.')[0]
        return datetime.strptime(combined, '%Y-%m-%d %H:%M:%S')

    @staticmethod
    def _sensor_from_platform(
            platform: str
    ) -> str:
        """
        Get the sensor name from the abbrevated platform name.

        :param platform:
            Landsat platform name (e.g., LC09).
        :return:
            Sensor name (e.g., Operational_Land_Imager).
        """
        landsat_platform_number = int(platform[2:4])
        landsat_platform_full_name = f'LANDSAT_{landsat_platform_number}'
        return platform_sensor_mapping[landsat_platform_full_name]

    def _preprocess_band_selection(
            self,
            in_dir: Path | Dict[str, str],
            band_selection: Optional[List[str]] = None,
            read_qa: Optional[bool] = True,
            read_atcor: Optional[bool] = False
    ):
        """
        Process the user-defined band selection if any and return the available
        bands in a pandas DataFrame.

        :param in_dir:
            Path to the directory containing the Landsat data or collection of
            hyper-links in the case of STAC. If a dictionary is passed, we assume
            that all files are stored in the same directory.
        :param band_selection:
            List of bands to be loaded. If None, all bands will be loaded.
            The bands loaded depend on the sensor, e.g., TM, ETM, OLI, TIRS.
            The sensor will be auto-detected. To make sure, the band selection
            works for multiple sensors, use the aliases defined in
            `~eodal.utils.constants.landsat_mapper.landsat_band_mapping`.
            For instance, to load the VIS bands pass `["blue", "green", "red"]`.
        :param read_qa:
            If True, the QA bands will be loaded as well. Default is True.
        :param read_atcor:
            If True, the bands stemming from the atmospheric correction are read
            as well. Default is False.
        :return:
            Pandas DataFrame with the available bands.
        """
        # get available bands
        available_bands = self._get_available_bands(in_dir)

        # check which platform and hence sensor is used
        platform = self._check_platform(in_dir)

        # get the sensor name from the platform
        sensor = self._sensor_from_platform(platform)
        sensor_bands = landsat_band_mapping[sensor]

        # compare against the band selection. In case the user passed the
        # sensor specific names (e.g,. "TM_B1") we need to convert them to
        # the generic names (e.g., "blue")
        # convert available bands to their generic names first
        for available_band in available_bands:
            if available_band in sensor_bands.keys():
                available_bands[available_bands.index(available_band)] = \
                    sensor_bands[available_band]

        # then check the user-defined selection (if any)
        if band_selection is not None:
            for band_name in band_selection:
                if band_name not in available_bands:
                    if band_name in sensor_bands.keys():
                        band_selection[band_selection.index(band_name)] = \
                            sensor_bands[band_name]
                    else:
                        warnings.warn(
                            f'Band {band_name} not found - ' +
                            'remove it from selection')
                        band_selection.remove(band_name)
        else:
            band_selection = available_bands

        # check if the user wants to read the atmospheric correction bands
        atcor_bands = landsat_band_mapping['atmospheric_correction']
        for atcor_band in atcor_bands:
            if atcor_band in available_bands:
                # read_atcor is True:
                # add those bands to the band selection that are available
                if read_atcor:
                    if not atcor_band in band_selection:
                        band_selection.append(atcor_band)
                # read_atcor is False:
                # remove atmospheric correction bands
                else:
                    if atcor_band in band_selection:
                        band_selection.remove(atcor_band)
            else:
                # band_selection.remove(atcor_band)
                pass

        # check if the user wants to read the QA bands
        qa_bands = landsat_band_mapping['quality_flags']
        for qa_band in qa_bands:
            if qa_band in available_bands:
                # read_qa is True:
                # add those bands to the band selection that are available
                if read_qa:
                    if not qa_band in band_selection:
                        band_selection.append(qa_band)
                # read_atcor is False:
                # remove atmospheric correction bands
                else:
                    if qa_band in band_selection:
                        band_selection.remove(qa_band)
            else:
                # band_selection.remove(qa_band)
                pass
 
        # next, we need the paths to the bands
        band_list = []
        for band_name in band_selection:
            if isinstance(in_dir, dict):
                if Settings.STAC_BACKEND == STAC_Providers.MSPC:
                    band_fpath = planetary_computer.sign(in_dir[band_name]["href"])
                else:
                    band_fpath = in_dir[band_name]["href"]
            elif isinstance(in_dir, Path):
                # for local resources, we have to use the sensor specific names
                # to find the bands
                sensor_specific_band_name = [
                    k for k, v in sensor_bands.items() if v == 'red'][0]
                band_fpath = in_dir.glob(f"*_{sensor_specific_band_name}.TIF")[0]
            band_res = None
            if band_name in sensor_bands.values():
                band_res = band_resolution[sensor][band_name]
            elif read_qa or band_name in qa_bands:
                band_res = band_resolution['quality_flags'][band_name]
            elif read_atcor or band_name in atcor_bands:
                band_res = band_resolution['atmospheric_correction'][band_name]

            item = {
                'band_name': band_name,
                'band_path': band_fpath,
                'band_resolution': band_res}
            band_list.append(item)

        # construct pandas DataFrame with all band entries and return
        band_df = pd.DataFrame(band_list)
        band_df.dropna(inplace=True)

        return band_df

    @classmethod
    def from_usgs(
        cls,
        in_dir: Path | Dict[str, str],
        band_selection: Optional[List[str]] = None,
        read_qa: Optional[bool] = True,
        read_atcor: Optional[bool] = False,
        apply_scaling: Optional[bool] = True,
        **kwargs
    ):
        """
        Load Landsat Level-2 science products (spectral bands, thermal bands,
        QA bands) into a EOdal `RasterCollection.

        :param in_dir:
            Path to the directory containing the Landsat data or collection of
            hyper-links in the case of STAC. If a dictionary is passed, we assume
            that all files are stored in the same directory.
        :param band_selection:
            List of bands to be loaded. If None, all bands will be loaded.
            The bands loaded depend on the sensor, e.g., TM, ETM, OLI, TIRS.
            The sensor will be auto-detected. To make sure, the band selection
            works for multiple sensors, use the aliases defined in
            `~eodal.utils.constants.landsat_band_mapping`. For instance, to load
            the VIS bands pass `["blue", "green", "red"]`.
        :param read_qa:
            If True, the QA bands will be loaded as well. Default is True.
        :param read_atcor:
            If True, the bands stemming from the atmospheric correction are read
            as well. Default is False.
        :param apply_scaling:
            If True, scales reflectance values to the range [0, 1] from original
            unsigned 16-bit integers. Default is True.
        :param kwargs:
            Additional keyword arguments passed to the `RasterCollection` constructor.
        :return:
            RasterCollection containing the Landsat bands.
        """
        # check band selection and determine the platform and sensor
        band_df = cls._preprocess_band_selection(
            cls,
            in_dir=in_dir,
            band_selection=band_selection,
            read_qa=read_qa,
            read_atcor=read_atcor)

        # check the clipping extent of the raster with the lowest (coarsest) spatial
        # resolution and remember it for all other bands with higher spatial
        # resolutions.
        # By doing so, it is ensured that all bands will be clipped to the same spatial
        # extent regardless of their pixel size. This works since all Landsat bands
        # share the same coordinate origin.
        # get lowest spatial resolution (maximum pixel size) band
        masking_after_read_required = False

        if kwargs.get("vector_features") is not None:
            bounds_df, shape_mask, lowest_resolution = adopt_vector_features_to_mask(
                band_df=band_df,
                vector_features=kwargs.get("vector_features")
            )
            if not kwargs.get("full_bounding_box_only", False):
                masking_after_read_required = True
            # update the vector_features entry
            kwargs.update({"vector_features": bounds_df})

        # get platform, sensor and sensing time
        platform = cls._check_platform(in_dir=in_dir)
        sensor = cls._sensor_from_platform(platform=platform)
        sensing_time = cls._sensing_time_from_filename(in_dir=in_dir)
        # get the product uri
        product_uri = cls._product_uri_from_filename(in_dir=in_dir)
        # determine processing level
        if sensor in \
            ['Multispectral_Scanner_System_L1-3',
             'Multispectral_Scanner_System_L4-5']:
            processing_level = ProcessingLevels.L1C
        else:
            processing_level = ProcessingLevels.L2A

        # construct the SceneProperties object
        scene_properties = SceneProperties(
            platform=f'LANDSAT_{platform[-1]}',
            sensor=sensor,
            acquisition_time=sensing_time,
            product_uri=product_uri,
            processing_level=processing_level
        )

        # set proper scaling factors to allow for conversion to
        # reflectance [0, 1]
        gain, offset = 1, 0
        if processing_level == ProcessingLevels.L2A:
            gain, offset = 0.00001, 0.0

        # loop over bands and add them to the collection of bands
        landsat = cls(scene_properties=scene_properties)
        for band_name in list(band_df.band_name):
            # get entry from dataframe with file-path of band
            band_safe = band_df[band_df.band_name == band_name]
            band_fpath = band_safe.band_path.values[0]

            # get alias name of band
            band_alias = None
            if band_name in landsat_band_mapping[sensor].values():
                band_alias = [
                    k for k, v in landsat_band_mapping[sensor].items()
                    if v == band_name][0]
            elif band_name in landsat_band_mapping['quality_flags'].keys() \
                    or band_name in landsat_band_mapping['quality_flags'].values():
                band_alias = band_name.lower()
            elif band_name in landsat_band_mapping['atmospheric_correction'].keys() \
                    or band_name in landsat_band_mapping['atmospheric_correction'
                                                         ].values():
                band_alias = band_name.lower()

            # read band
            try:
                if band_name in landsat_band_mapping[sensor].values():
                    kwargs.update({'scale': gain, 'offset': offset})
                landsat.add_band(
                    Band.from_rasterio,
                    fpath_raster=band_fpath,
                    band_idx=1,
                    band_name_dst=band_name,
                    band_alias=band_alias,
                    **kwargs,
                )
            except Exception as e:
                raise Exception(
                    f"Could not add band {band_name} " +
                    f"from {scene_properties.product_uri}: {e}"
                )
            # apply actual vector features if masking is required
            if masking_after_read_required:
                # nothing to do when the lowest resolution is passed
                if band_safe.band_resolution.values == lowest_resolution:
                    continue
                # otherwise resample the mask of the lowest resolution to the
                # current resolution using nearest neighbor interpolation
                tmp = shape_mask.astype("uint8")
                dim_resampled = (landsat[band_name].ncols, landsat[band_name].nrows)
                res = cv2.resize(
                    tmp, dim_resampled, interpolation=cv2.INTER_NEAREST_EXACT
                )
                # cast back to boolean
                mask = res.astype("bool")
                landsat.mask(mask=mask, bands_to_mask=[band_name], inplace=True)

        # scaling of reflectance values (i.e., do not scale SCL)
        if apply_scaling:
            sel_bands = landsat.band_names
            # only scale the reflectance bands
            sel_bands = [x for x in sel_bands if x in
                         landsat_band_mapping[sensor].values()]
            landsat.scale(
                inplace=True,
                band_selection=sel_bands,
                pixel_values_to_ignore=[landsat[landsat.band_names[0]].nodata],
            )

        return landsat

    def calc_si(
        self,
        si_name: str,
        inplace: Optional[bool] = False,
        band_mapping: Optional[Dict[str, str]] = {}
    ) -> None | np.ndarray | np.ma.MaskedArray:
        """
        Calculates a spectral index based on color-names (set as band aliases)

        :param si_name:
            name of the spectral index to calculate (e.g., 'NDVI').
        :param inplace:
            if False, returns the calculated SI as numpy array (default), else
            adds the calculated SI as a new band to the RasterCollection
            object.
        :param band_mapping:
            ..versionadd 0.2.2::
            optional band mapping to use different color names instead
            of the default ones (e.g., nir_2 instead of nir_1 as default
            near-infrared band, which might be helpful for some sensor
            with more than one NIR band such as Sentinel-2 MSI).
            See ~`eodal.core.spectral_indices.SpectralIndices` how
            `band_mapping` must look like.
        """

        # set color names properly before calling SI class
        # (background: EOdal internally uses slightly different color names
        # compared to Landsat collection 2 products. The differences
        # only affect the NIR and SWIR bands)
        if len(band_mapping) == 0:
            band_mapping = {
                'nir_1': 'nir08',
                'swir_1': 'swir16',
                'swir_2': 'swir22'
            }
        return RasterCollection.calc_si(
            self, si_name=si_name, inplace=inplace,
            band_mapping=band_mapping)

    def get_water_mask(
            self,
            mask_band: Optional[str] = 'qa_pixel',
            inplace: Optional[bool] = False,
            name_water_mask: Optional[str] = 'water_mask'
    ) -> Band | None:
        """
        Get a water mask from the pixel quality band (bit 7).

        NOTE:
            Since the `mask_band` can be set to *any* `Band` it is also
            possible to use a different water mask, e.g., from
            a custom classifier as long as the bit map used for the classes
            is the same.
            See also
            https://www.usgs.gov/media/images/landsat-collection-2-pixel-quality-assessment-bit-index
            for more details.

        :param mask_band:
            The name of the band to use for masking. Default is 'qa_pixel'.
        :param inplace:
            Whether to return a new `Band` instance or add a `Band` to the
            current `Landsat` instance. Default is False.
        :param name_water_mask:
            The name of the water mask band. Default is 'water_mask'.
        :return:
            A `Band` instance containing the water mask or `None` if
            `inplace` is True.
        """
        water_mask = self.mask_from_qa_bits(
            bit_range=(7, 7),
            band_name=mask_band
        )
        water_mask_band = Band(
                band_name=name_water_mask,
                values=water_mask,
                geo_info=self[mask_band].geo_info,
                nodata=0,
            )
        if inplace:
            self.add_band(water_mask_band)
            return None
        else:
            return water_mask_band

    def mask_from_qa_bits(
            self,
            bit_range: tuple,
            band_name: Optional[str] = 'qa_pixel'
    ) -> np.ndarray | np.ma.MaskedArray:
        """
        Extract Quality Accurance (QA) bits from the QA band of
        Landsat to obtain a binary mask.

        This function can be used to obtain a binary cloud or
        cloud shadow mask, for example.

        :param bit_range:
            A tuple of two integers indicating the start and end bit
            of the bit range to extract.
        :param band_name:
            The name of the QA band. Default is 'qa_pixel'.
        :return:
            A 2-dimensional numpy array containing the obtained mask.
        """
        # get the band
        band = deepcopy(self[band_name].values)
        band_mask = None
        if isinstance(band, np.ndarray):
            band_data = band
        elif isinstance(band, np.ma.MaskedArray):
            band_data = band.data
            band_mask = band.mask
        # compute the bits to extract
        pattern = 0
        for i in range(bit_range[0], bit_range[1] + 1):
            pattern += 2 ** i
        # assign the extracted bits to the band
        band_data = np.bitwise_and(band_data, pattern)
        band_data = np.right_shift(band_data, bit_range[0])

        # create a masked array if the input was also masked
        if band_mask is not None:
            band_data = np.ma.MaskedArray(
                data=band_data,
                mask=band_mask
            )

        return band_data

    def mask_clouds_and_shadows(
            self,
            bands_to_mask: Optional[list[str]] = None,
            cloud_classes: Optional[list[int]] = [1, 2, 3, 5],
            mask_band: Optional[str] = 'qa_pixel',
            **kwargs
    ) -> None | Landsat:
        """
        A wrapper around the inherited ``mask`` method to mask cirrus,
        cloud and cloud shadow pixels in Landsat scenes based on the
        pixel quality band.

        NOTE:
            Since the `mask_band` can be set to *any* `Band` it is also
            possible to use a different cloud/shadow etc. mask, e.g., from
            a custom classifier as long as the bit map used for the classes
            is the same.
            See also
            https://www.usgs.gov/media/images/landsat-collection-2-pixel-quality-assessment-bit-index
            for more details.

        NOTE:
            You might also use the mask function from
            `eodal.core.raster.RasterCollection` directly.

        :param bands_to_mask:
            A list of bands to mask. Default is all bands.
        :param cloud_classes:
            A list of integers indicating the cloud classes to mask.
            Default is [1, 2, 3, 5].
        :param mask_band:
            The name of the band to use for masking. Default is 'qa_pixel'.
        :param kwargs:
            optional kwargs to pass to `~eodal.core.raster.RasterCollection.mask`
        :returns:
            depending on `inplace` (passed in the kwargs) a new `Sentinel2` instance
            or None
        """
        if bands_to_mask is None:
            bands_to_mask = self.band_names
        # the mask band should never be masked
        if mask_band in bands_to_mask:
            bands_to_mask.remove(mask_band)
        try:
            mask_list = []
            for cloud_class in cloud_classes:
                # construct the bit range
                bit_range = (cloud_class, cloud_class)
                # get the binary mask as boolean array
                mask = self.mask_from_qa_bits(
                    bit_range=bit_range,
                    band_name=mask_band).astype('bool')
                # add the mask to the list
                mask_list.append(mask)

            # combine the masks
            cloud_mask = np.any(mask_list, axis=0)
            # mask the bands
            return self.mask(
                mask=cloud_mask,
                bands_to_mask=bands_to_mask,
                **kwargs
            )
        except Exception as e:
            raise Exception(f"Could not mask clouds and shadows: {e}")
