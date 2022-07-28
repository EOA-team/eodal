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
    def from_ms_pc(
            cls,
            sensing_date: date,
            polarizations: Optional[str] = ['VV', 'VH'],
            **kwargs
        ):
        """
        """
        # a bounding box (vector features) is required
        vector_features = kwargs.get('vector_features', None)
        if 'vector_features' is None:
            raise ValueError('A bounding box (vector_features) must be specified')
        # check STAC provider and status
        if not Settings.USE_STAC:
            raise ValueError('This method requires STAC')
        if Settings.STAC_BACKEND != STAC_Providers.MSPC:
            raise ValueError('This method requires Microsoft Planetary Computer')
        if Settings.PC_SDK_SUBSCRIPTION_KEY == '':
            raise ValueError('This method requires a valid Planetary Computer API key')

        # query the catalog
        if isinstance(vector_features, Path):
            vector_features = gpd.read_file(vector_features)
        # construct the bounding box from vector features
        # the bbox must be provided as a polygon in geographic coordinates
        vector_features.to_crs(epsg=4326, inplace=True)
        bbox = vector_features.total_bounds
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1"
        )
        search = catalog.search(
            collections=["sentinel-1-rtc"], bbox=bbox , datetime=sensing_date.strftime('%Y-%m-%d')
        )
        items = search.get_all_items()
        # it might happen that no item was found for a given date. In this case
        # re-do the search without the datetime filter and return the item that is
        # closest to the sensing_date passed
        if len(items) == 0:
            search = catalog.search(
                collections=["sentinel-1-rtc"], bbox=bbox
            )
            items = search.get_all_items()
            time_diffs = []
            for item in items:
                item_date = datetime.strptime(item.properties['datetime'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
                time_diff = item_date - sensing_date
                # save the absolute time difference, otherwise argmin makes no sense
                time_diffs.append(abs(time_diff))
            time_diff_argmin = np.argmin(time_diffs)
            items = items[time_diff_argmin]

        # sign requests (required to have read access to the data)
        if not isinstance(items, ItemCollection):
            items = [items]
        signed_items = []
        for item in items:
            signed_items.append(planetary_computer.sign_item(item))
        # TODO: read polarization (files) and properties -> save into own class as for S2

            
            