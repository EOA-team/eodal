"""
Accessing Planet-Scope data
"""

from __future__ import annotations

import geopandas as gpd

from pathlib import Path
from typing import List, Optional, Tuple, Union

from eodal.core.raster import RasterCollection
from eodal.utils.constants.planet_scope import (
    super_dove_band_mapping,
    super_dove_gain_factor,
)
from eodal.utils.exceptions import BandNotFoundError


class PlanetScope(RasterCollection):
    @staticmethod
    def _process_band_selection(
        band_selection: List[str], platform: str
    ) -> Tuple[List[str]]:
        """
        Translates the band names provided by the user to those
        set by Planet and returns the corresponding aliases

        :param band_selection:
            selection of spectral bands
        :param platform:
            Planet satellite platform (e.g., 'SuperDove')
        :returns:
            tuple with band names in the first and band aliases in the second
            entry
        """
        if platform == "SuperDove":
            new_band_selection = []
            new_band_aliases = []
            for band in band_selection:
                if band in super_dove_band_mapping.keys():
                    new_band_selection.append(super_dove_band_mapping[band])
                    new_band_aliases.append(band)
                elif band in super_dove_band_mapping.values():
                    new_band_selection.append(band)
                    pos = list(super_dove_band_mapping.values()).index(band)
                    new_band_aliases.append(list(super_dove_band_mapping.keys())[pos])
                else:
                    raise BandNotFoundError(
                        f"{band} is not a valid band for PS SuperDove"
                    )
        else:
            raise NotImplementedError(f"{platform} is not implemented")
        return new_band_selection, new_band_aliases


class SuperDove(PlanetScope):
    @classmethod
    def from_analytic(
        cls,
        in_dir: Path,
        band_selection: Optional[List[str]] = None,
        read_ql: Optional[bool] = True,
        apply_scaling: Optional[bool] = True,
        **kwargs,
    ):
        """
        Loads a PS Super Dove scene into a RasterCollection object.

        :param in_dir:
            directory containing the scene-data
        :param band_selection:
            selection of bands to read. By default all bands are read.
        :param read_ql:
            If True (default) reads the quality layers from the udm2 file
            (usable data mask).
        :param apply_scaling:
            If True scales the reflectance factors between 0 and 1 based
            on gain and offset.
        :param kwargs:
            optional keyword arguments to pass to
            `~eodal.core.raster.RasterCollection.from_multi_band_raster`
        """
        # read the surface reflectance file
        sr_file = next(in_dir.glob("*_SR_8b.tif"))
        band_names, band_aliases = None, None
        # process the band selection
        if band_selection is not None:
            band_names, band_aliases = cls._process_band_selection(
                band_selection, platform="SuperDove"
            )
        sr = cls.from_multi_band_raster(
            fpath_raster=sr_file,
            band_names_src=band_names,
            band_names_dst=band_names,
            band_aliases=band_aliases,
            scale=super_dove_gain_factor,
            **kwargs,
        )
        # apply scaling if selected
        if apply_scaling:
            sr.scale(inplace=True)
        # read udm2 (usable data mask) if selected
        # see also: https://developers.planet.com/docs/data/udm-2/
        if read_ql:
            udm_file = next(in_dir.glob("*_udm2.tif"))
            udm = RasterCollection.from_multi_band_raster(
                fpath_raster=udm_file, **kwargs
            )
            for udm_band in udm.band_names:
                sr.add_band(udm[udm_band])
        return sr

    def mask_non_clear_pixels(self, confidence_threshold: Optional[int] = 100):
        """
        Mask out non-clear pixels and keep only clear pixels with a certain
        confidence threshold (100% by default).

        :param confidence_treshold:
            threshold [0-100] to treat a clear pixel as truely pixel. The higher
            the threshold the more confident the algorithm was that the pixel
            was clear. Set to 100 (maximum confidence) by default.
        """
        # check if clear and confidence band are available
        if not set(["clear", "confidence"]).issubset(set(self.band_names)):
            raise BandNotFoundError('"clear" and/or "confidence" are missing')
        clear_mask = self["clear"] == 0
        confidence_mask = self["confidence"] < confidence_threshold
        # combine clear and confidence mask
        mask = clear_mask and confidence_mask
        # apply mask
        self.mask(mask.values.data, inplace=True)

    @classmethod
    def read_pixels(
        cls,
        in_dir: Path,
        vector_features: Union[Path, gpd.GeoDataFrame],
        band_selection: Optional[List[str]] = None,
        read_ql: Optional[bool] = True,
        apply_scaling: Optional[bool] = True,
    ) -> gpd.GeoDataFrame:
        """
        Extracts PlanetScope Super Dove raster values at locations defined by one or many
        vector geometry features read from a vector file (e.g., ESRI shapefile) or
        ``GeoDataFrame``.

        :param in_dir:
            Planet Scope SuperDove scene from which to extract
            pixel values at the provided point locations
        :param point_features:
            vector file (e.g., ESRI shapefile or geojson) or ``GeoDataFrame``
            defining point locations for which to extract pixel values
        :param band_selection:
            list of bands to read. Per default all raster bands available are read.
        :param read_ql:
            read quality layer file (udm2, usuable data mask)
        :param apply_scaling:
            apply SuperDove gain and offset factor to derive reflectance values scaled
            between 0 and 1.
        :returns:
            ``GeoDataFrame`` containing the extracted raster values. The band values
            are appened as columns to the dataframe. Existing columns of the input
            `in_file_pixels` are preserved.
        """
        # process the band selection
        band_names = None
        if band_selection is not None:
            band_names, _ = cls._process_band_selection(
                band_selection, platform="SuperDove"
            )
        # read surface reflectance values
        sr_file = next(in_dir.glob("*_SR_8b.tif"))
        sr = RasterCollection.read_pixels(
            fpath_raster=sr_file,
            vector_features=vector_features,
            band_names_src=band_names,
            band_names_dst=band_names,
        )
        # skip no-data pixels (surface reflectance is zero in all bands)
        if band_names is None:
            band_names = super_dove_band_mapping.values()
            sr = sr.loc[~(sr[band_names] == 0).all(axis=1)]
        # apply scaling if selected
        if apply_scaling:
            for band_name in band_names:
                sr[band_name] = sr[band_name].apply(
                    lambda x, super_dove_gain_factor=super_dove_gain_factor: x
                    * super_dove_gain_factor
                )
        # extract udm if selected
        if read_ql:
            udm_file = next(in_dir.glob("*_udm2.tif"))
            sr = RasterCollection.read_pixels(
                fpath_raster=udm_file, vector_features=vector_features
            )
        return sr


if __name__ == "__main__":
    scene = Path(
        "/home/graflu/public/Evaluation/Satellite_data/Planet/Eschikon/PSB_SD/analytic_8b_sr_udm2/2022/20220307_095705_17_2473"
    )
    band_selection = ["blue", "green", "red"]
    parcel = Path(
        "/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Hohrueti.shp"
    )
    ds = SuperDove.from_analytic(
        in_dir=scene, band_selection=band_selection, vector_features=parcel
    )
    ds.mask_non_clear_pixels()

    fpath_pixels = Path(
        "/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/Sampling_Points/Bramenwies.shp"
    )
    pixels = SuperDove.read_pixels(vector_features=fpath_pixels, in_dir=scene)
