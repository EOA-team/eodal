'''
Created on Jul 28, 2022

@author: graflu
'''

import geopandas as gpd
import numpy as np
import planetary_computer
import pystac_client

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from eodal.config import get_settings, STAC_Providers
from eodal.core.raster import RasterCollection
from pystac.item_collection import ItemCollection

Settings = get_settings()

class Sentinel1(RasterCollection):
    pass

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
            polarizations: Optional[str] = ['VV', 'VH'],
            **kwargs
        ):
        """
        """
        pass

    def cross_ratio(self):
        pass

            
            