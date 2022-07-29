'''
Created on Jul 27, 2022

@author: graflu
'''

import geopandas as gpd
import json
import requests

from datetime import date, datetime
from pathlib import Path
from requests.models import Response
from requests.sessions import Session
from shapely.geometry import box
from typing import Any, Dict, List, Optional

from eodal.config import get_settings

Settings = get_settings()
orders_url = 'https://api.planet.com/compute/ops/orders/v2'
data_url = 'https://api.planet.com/data/v1'

class APIError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class PlanetAPIClient(object):

    def __init__(
            self,
            request: Dict[str, Any] = {},
            features: List[Dict[str, Any]] = []
        ):
        self.request = request
        self.features = features

    @staticmethod
    def authenticate(url: str) -> Session:
        """
        Authentication for using the Planet (orders) API
    
        :param url:
            API endpoint for testing authentication
        :returns:
            authenticated session object
        """
        # open a session and try to authenticate
        session = requests.Session()
        session.auth = (Settings.PLANET_API_KEY, '')
        response = session.get(url)
        # make sure authentication was successful (return code 200)
        if response.status_code != 200:
            raise AuthenticationError(
                f'[HTTP:{response.status_code}] Could not authenticate at {url}: {response.text}')
        return session

    @staticmethod
    def date_to_planet_dt(date_to_convert: date) -> str:
        """
        Converts datetime.date to format required by Planet API
    
        :param date_to_convert:
            date to convert
        :returns:
            string in time format required by Planet
        """
        timestamp = datetime(*date_to_convert.timetuple()[:-2])
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def place_order(request, auth):
        response = requests.post(orders_url, data=json.dumps(request), auth=auth, headers=headers)
        print(response)
    
        if not response.ok:
            raise Exception(response.content)
        
        order_id = response.json()['id']
        print(order_id)
        order_url = orders_url + '/' + order_id
        return order_url

    @staticmethod
    def quicksearch(session: Session, request_data: Dict[str, Any]) -> Response:
        """
        Queries the Planet Data API based on user-defined request.
    
        This returns available datasets but does not place a order!
    
        :param session:
            authenticated session object
        :param request_data:
            search request in format required by Planet Data and Orders API
        :returns:
            `Response` object whose json attribute contains the features found
        """
        quick_url = f'{data_url}/quick-search'
        # post request to the API quick search endpoint
        response = session.post(quick_url, json=request_data)
        if response.status_code != 200:
            raise APIError(
                f'[HTTP:{response.status_code}] Could not query {quick_url}: {response.text}')
        return response

    @classmethod
    def query_planet_api(
            cls,
            start_date: date,
            end_date: date,
            bounding_box: Path | gpd.GeoDataFrame,
            instrument: Optional[str] = 'PSB.SD',
            item_type: Optional[str] = 'PSScene',
            cloud_cover_threshold: Optional[int] = 100
        ):
        """
        Queries the Planet API to retrieve available datasets (no download,
        no order placement).
    
        :param start_date:
            start date of the queried time period (inclusive)
        :param end_date:
            end date of the queried time period (inclusive)
        :param bounding_box:
            file with vector feature(s) or `GeoDataFrame` with 1:N features.
            The bounding box encompassing all features is taken.
        :param instument:
            instrument (satelitte platform) from which to download data.
            `PSB.SD` (Planet Super Dove) by default.
        :param item_type:
            Planet product item type. `PSScene` by default.
        :param cloud_cover_threshold:
            cloudy pixel percentage threshold (0-100%) for filtering
            too cloudy scenes
        :returns:
        
        """
        # open authenticated session
        session = cls.authenticate(url=orders_url)
    
        # check bounding box; re-project to WGS84 if necessary
        if isinstance(bounding_box, Path):
            bbox = gpd.read_file(bounding_box)
        elif isinstance(bounding_box, gpd.GeoDataFrame):
            bbox = bounding_box.copy()
        else:
            raise TypeError('bounding_box must be Path object or GeoDataFrame')
        bbox.to_crs(epsg=4326, inplace=True)
        # get total bounds as geojson (required by API)
        bbox_poly = box(*bbox.total_bounds)
        bbox_json = gpd.GeoSeries([bbox_poly]).to_json()
        bbox_feature = json.loads(bbox_json)['features'][0]['geometry']
    
        # scale cloud cover between 0 and 1
        cloud_cover_threshold *= 0.01
    
        # adjust date time format required by Planet API
        start_time = cls.date_to_planet_dt(date_to_convert=start_date)
        end_time = cls.date_to_planet_dt(date_to_convert=end_date)
    
        # define the date filter
        date_filter = {
            "type": "DateRangeFilter",
            "field_name": "acquired",
            "config": {
                "gte": start_time,
                "lte": end_time
            }
        }
        
        # define geometry filter
        geom_filter ={
            "type": "GeometryFilter",
            "field_name": "geometry",
            "config": bbox_feature
        }
        
        # define cloud cover filter with less than 50% cloud coverage
        cloud_cover_filter = {
            "type": "RangeFilter",
            "field_name": "cloud_cover",
            "config":{
                "lte": cloud_cover_threshold
            }
        }
    
        # define instrument filter
        instrument_filter = {
            "type": "StringInFilter",
            "field_name": "instrument",
            "config": [instrument]
        }
    
        # put all filters together
        andfilter = {
            "type": "AndFilter",
            "config": [date_filter, instrument_filter, geom_filter, cloud_cover_filter]
        }
    
        # setup the request for the API
        request_data = {
            "item_types": [item_type],
            "filter": andfilter
        }
    
        response = cls.quicksearch(session=session, request_data=request_data)
        features = response.json()["features"]

        return cls(response, features)
    

    

    


if __name__ == '__main__':

    start_date = date(2022,7,25)
    end_date = date(2022,7,29)
    bounding_box = Path('/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/MA_Supervision/22_Samuel-Wildhaber/LAI_analysis_BW/data/pl_BW_median.gpkg')
    order_name = 'Bramenwies_test'
    cloud_cover = 50.

    api_response = PlanetAPIClient.query_planet_api(
        start_date=start_date,
        end_date=end_date,
        bounding_box=bounding_box,
        cloud_cover_threshold=cloud_cover
    )
    
    