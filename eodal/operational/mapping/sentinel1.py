'''
Created on Aug 9, 2022

@author: graflu
'''

import geopandas as gpd

from datetime import date
from shapely.geometry import box
from typing import Any, Union

from eodal.config import get_settings
from eodal.core.sensors import Sentinel1
from .mapper import Mapper

settings = get_settings()

class Sentinel1Mapper(Mapper):
    """
    Spatial mapper class for Sentinel-1 data.
    """
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        """
        Initializes a new Sentinel-1 Mapper object

        :param args:
            arguments to pass to the constructor of the ``Mapper`` super class
        :param kwargs:
            key-word arguments to pass to the constructor of the ``Mapper``
            super class
        """
        # initialize super-class
        Mapper.__init__(self, *args, **kwargs)

    def get_scenes(self) -> None:
        """
        Queries the Sentinel-1 metadata catalog for a selected time period and
        feature collection.

        The scene selection and processing workflow contains several steps:

        1.  Query the metadata catalog for **ALL** available scenes that overlap
            the bounding box of a given ``Polygon`` or ``MultiPolygon``
            feature.
        2.  Check if for a single sensing date several scenes are available
        3.  If yes check if that's due to Sentinel-1 tiling grid design. If yes
            flag these scenes as potential merge candidates.
        4.  If the scenes found have different spatial coordinate systems (CRS)
            (usually different UTM zones) flag the data accordingly. The target
            CRS is defined as that CRS the majority of scenes shares.
        """
        self._get_scenes(sensor='sentinel1')

    def get_observation(
        self, feature_id: Any, sensing_date: date, **kwargs
    ) -> Union[gpd.GeoDataFrame, Sentinel1, None]:
        """
        Returns the scene data (observations) for a selected feature and date.

        If for the date provided no scenes are found, the data from the scene(s)
        closest in time is returned

        :param feature_id:
            identifier of the feature for which to extract observations
        :param sensing_date:
            date for which to extract observations (or the closest date if
            no observations are available for the given date)
        :param kwargs:
            optional key-word arguments to pass on to
            `~eodal.core.sensors.Sentinel2.from_safe`
        :returns:
            depending on the geometry type of the feature either a
            ``GeoDataFrame`` (geometry type: ``Point``) or ``Sentinel2Handler``
            (geometry types ``Polygon`` or ``MultiPolygon``) is returned. if
            the observation contains nodata, only, None is returned.
        """
        res = self._get_obervation(feature_id=feature_id, sensing_date=sensing_date,
                                    sensor='sentinel1', **kwargs)
        if isinstance(res, tuple):
            _, scenes_date, feature_gdf = res
            # TODO: merge logic according to Sentinel-2
        return res

    def get_complete_timeseries(self):
        pass

# TODO
if __name__ == '__main__':

    from eodal.metadata.stac import sentinel1 as s1_stac_client
    from eodal.core.sensors import Sentine1 
    import matplotlib.pyplot as plt
    from datetime import date
    from pathlib import Path

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    # provide bounding box
    bounding_box_fpath = Path(
        # '/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Bramenwies.shp'
        '/mnt/ides/Lukas/software/eodal/data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp'
    )

    # Sentinel-1
    res_s1 = s1_stac_client(
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
            