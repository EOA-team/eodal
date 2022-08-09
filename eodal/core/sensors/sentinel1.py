'''
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
    get_S1_acquistion_time_from_safe, _url_to_safe_name, \
    get_s1_imaging_mode_from_safe

Settings = get_settings()

class Sentinel1(RasterCollection):
    """
    Reading Sentinel-1 Radiometrically Terrain Corrected (RTC) and
    Ground Range Detected (GRD) products
    """

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
            else:
                # TODO: add support for reading files from local data source
                pass
            band_items.append(item)
        return pd.DataFrame(band_items)

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
            mode = get_s1_imaging_mode_from_safe(dot_safe_name=in_dir)
        except Exception as e:
            raise ValueError(f'Could not determine imaging mode: {e}')
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
            mode=mode
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

    from eodal.metadata.stac import sentinel1
    import matplotlib.pyplot as plt

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    # provide bounding box
    bounding_box_fpath = Path(
        # '/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Bramenwies.shp'
        '/mnt/ides/Lukas/software/eodal/data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp'
    )

    # Sentinel-1
    res_s1 = sentinel1(
        date_start=date_start,
        date_end=date_end,
        vector_features=bounding_box_fpath,
        collection='sentinel-1-rtc'
    )
    res_s1 = res_s1.sort_values(by='datetime')


    f, ax = plt.subplots(nrows=1, ncols=res_s1.shape[0], figsize=(20,5), sharex=True)

    # loop datasets and plot CR
    for idx, rec in res_s1.iterrows():
        asset = rec['assets']
    
        s1 = Sentinel1.from_safe(in_dir=asset, vector_features=bounding_box_fpath)
        s1.calc_si('CR', inplace=True)

        s1.plot_band('CR', ax=ax[idx], colorbar_label='CR [-]', vmin=0, vmax=4)
        if idx > 0:
            ax[idx].set_ylabel('')
        ax[idx].set_title(f'{s1.scene_properties.acquisition_time}\n{s1.scene_properties.platform}')

    f.tight_layout()
    f.savefig('/mnt/ides/Lukas/software/eodal/img/sentinel1_cr.png', bbox_inches='tight')
    plt.close(f)
            