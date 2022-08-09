'''
Created on Jul 28, 2022

@author: graflu
'''

import pandas as pd
import planetary_computer

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from eodal.config import get_settings
from eodal.core.band import Band
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneProperties
from eodal.utils.sentinel1 import get_S1_platform_from_safe, \
    get_S1_acquistion_time_from_safe, _url_to_safe_name

Settings = get_settings()

class Sentinel1(RasterCollection):

    @staticmethod
    def _get_band_files(in_dir: Path | Dict[str, str], polarizations: List[str]) -> pd.DataFrame:
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
            # get band files from STAC (MS PC)
            href = in_dir[polarization.lower()]['href']
            # sign href (this works only with a valid API key)
            href_signed = planetary_computer.sign_url(href)
            if Settings.USE_STAC:
                item = {
                    'polarization': polarization,
                    'file_path': href_signed
                }
            band_items.append(item)
        return pd.DataFrame(band_items)

class Sentinel1_RTC(Sentinel1):
    """
    Access to Sentinel-1 Radiometrically Terrain Corrected (RTC) products
    from Microsoft-Planetary Computer

    IMPORTANT
        For accessing the RTC products a valid Planetary Computer API key
        is required.
    """

    @classmethod
    def from_safe(
            cls,
            in_dir: Path | Dict[str, str],
            polarizations: Optional[List[str]] = ['VV', 'VH'],
            **kwargs
        ):
        """
        Reads a Sentinel-1 RTC (radiometrically terrain corrected) product

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
            raise ValueError(f'Could not determine platform: {e}')
        try:
            acqui_time = get_S1_acquistion_time_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f'Could not determine acquisition time: {e}')
        try:
            if isinstance(in_dir, Path):
                product_uri = in_dir.name
            elif Settings.USE_STAC:
                product_uri = _url_to_safe_name(in_dir)
        except Exception as e:
            raise ValueError(f'Could not determine product uri: {e}')

        # get a new RasterCollection
        scene_properties = SceneProperties(
            acquisition_time=acqui_time,
            platform=platform,
            sensor="SAR",
            product_uri=product_uri,
        )
        sentinel1 = cls(scene_properties=scene_properties)

        # add bands
        for _, band_item in band_df.iterrows():
            sentinel1.add_band(
                band_constructor=Band.from_rasterio,
                fpath_raster=band_item.file_path,
                band_name_dst=band_item.polarization,
                **kwargs
            )

        return sentinel1

if __name__ == '__main__':

    from eodal.metadata.stac import sentinel1_rtc

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    # provide bounding box
    bounding_box_fpath = Path(
        # '/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Bramenwies.shp'
        '/mnt/ides/Lukas/software/eodal/data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp'
    )

    # Sentinel-1
    res_s1 = sentinel1_rtc(
        date_start=date_start,
        date_end=date_end,
        vector_features=bounding_box_fpath
    )

    rec = res_s1.iloc[0]
    asset = rec['assets']

    s1 = Sentinel1_RTC.from_safe(in_dir=asset, vector_features=bounding_box_fpath)


            