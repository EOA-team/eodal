"""
Class for interacting with PlanetScope's Data and Order URL for checking
available mapper, placing orders and downloading data.

Make sure to have a Planet-account and to have exported your valid API key
as environmental variable. You can find your API following this link:
https://www.planet.com/account/#/user-settings

Under Linux you can set your API key by running:

.. code-block:: shell

    export PLANET_API_KEY = "<your-planet-api-key>"
    
Copyright (C) 2022 Samuel Wildhaber with some modifications by Lukas Valentin Graf

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
import json
import pandas as pd
import requests
import time

from alive_progress import alive_bar
from datetime import date, datetime
from pathlib import Path
from requests.models import Response
from requests.sessions import Session
from shapely.geometry import box
from typing import Any, Dict, List, Optional

from eodal.config import get_settings
from eodal.utils.exceptions import APIError, AuthenticationError
from eodal.utils.geometry import box_to_geojson

Settings = get_settings()
logger = Settings.logger

# order and data URL from Settings
orders_url = Settings.ORDERS_URL
data_url = Settings.DATA_URL


class PlanetAPIClient(object):
    """
    `eodal` Planet-API client.

    :attrib request:
        query parameters to pass to Planet-API (e.g.,
        date and dataset filters)
    :attrib features:
        features returned from Planet API (i.e., found
        Planet-Scope mapper)
    :attrib session:
        (authenticated) session object to interact with
        the Planet-API without re-sensing the API key for
        every single request
    """

    def __init__(
        self,
        request: Optional[Dict[str, Any]] = {},
        features: Optional[List[Dict[str, Any]]] = [{}],
        session: Optional[Session] = None,
    ):
        """
        Class constructor method

        :param request:
            query parameters to pass to Planet-API (e.g.,
            date and dataset filters)
        :param features:
            features returned from Planet API (i.e., found
            Planet-Scope mapper)
        :param session:
            (authenticated) session object to interact with
            the Planet-API without re-sensing the API key for
            every single request
        """
        self.request = request
        self.features = features
        self.session = session

    @property
    def features(self) -> List[Dict[str, Any]]:
        return self._features

    @features.setter
    def features(self, val: List[Dict[str, Any]]):
        if not isinstance(val, list):
            raise TypeError("Expected a list object")
        if not all([isinstance(x, dict) for x in val]):
            raise TypeError("all list elements must be dictionaries")
        self._features = val

    @property
    def request(self) -> Dict[str, Any]:
        return self._request

    @request.setter
    def request(self, val: Dict[str, Any]) -> None:
        if not isinstance(val, dict):
            raise TypeError("Expected a dictionary object")
        self._request = val

    @property
    def session(self) -> Session:
        return self._session

    @session.setter
    def session(self, val: Session):
        if not isinstance(val, Session) and val is not None:
            raise TypeError(
                "Expected a Session object " + "(requests.sessions.Session object)"
            )
        self._session = val

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
        quick_url = f"{data_url}/quick-search"
        # post request to the API quick search endpoint
        response = session.post(quick_url, json=request_data)
        if response.status_code != 200:
            raise APIError(
                f"[HTTP:{response.status_code}] Could not query {quick_url}: {response.text}"
            )
        return response

    @classmethod
    def query_planet_api(
        cls,
        start_date: date,
        end_date: date,
        bounding_box: Path | gpd.GeoDataFrame,
        instrument: Optional[str] = "PSB.SD",
        item_type: Optional[str] = "PSScene",
        cloud_cover_threshold: Optional[int] = 100,
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
            too cloudy mapper
        :returns:
            `PlanetAPIClient object'
        """
        # open authenticated session
        cls.authenticate(self=cls, url=orders_url)

        # check bounding box; re-project to WGS84 if necessary
        if isinstance(bounding_box, Path):
            bbox = gpd.read_file(bounding_box)
        elif isinstance(bounding_box, gpd.GeoDataFrame):
            bbox = bounding_box.copy()
        else:
            raise TypeError("bounding_box must be Path object or GeoDataFrame")
        # convert bounding box to geojson
        bbox_feature = box_to_geojson(gdf=bbox)

        # scale cloud cover between 0 and 1
        cloud_cover_threshold *= 0.01

        # adjust date time format required by Planet API
        start_time = cls.date_to_planet_dt(date_to_convert=start_date)
        end_time = cls.date_to_planet_dt(date_to_convert=end_date)

        # define the date filter
        date_filter = {
            "type": "DateRangeFilter",
            "field_name": "acquired",
            "config": {"gte": start_time, "lte": end_time},
        }

        # define geometry filter
        geom_filter = {
            "type": "GeometryFilter",
            "field_name": "geometry",
            "config": bbox_feature,
        }

        # define cloud cover filter with less than 50% cloud coverage
        cloud_cover_filter = {
            "type": "RangeFilter",
            "field_name": "cloud_cover",
            "config": {"lte": cloud_cover_threshold},
        }

        # define instrument filter
        instrument_filter = {
            "type": "StringInFilter",
            "field_name": "instrument",
            "config": [instrument],
        }

        # put all filters together
        andfilter = {
            "type": "AndFilter",
            "config": [date_filter, instrument_filter, geom_filter, cloud_cover_filter],
        }

        # setup the request for the API
        request_data = {"item_types": [item_type], "filter": andfilter}

        response = cls.quicksearch(session=cls.session, request_data=request_data)
        features = response.json()["features"]

        return cls(request=request_data, features=features, session=cls.session)

    def authenticate(self, url: str) -> None:
        """
        Authentication for using the Planet (orders) API

        :param url:
            API end-point for testing authentication
        """
        # open a session and try to authenticate
        self.session = requests.Session()
        self.session.auth = (Settings.PLANET_API_KEY, "")
        response = self.session.get(url)
        # make sure authentication was successful (return code 200)
        if response.status_code != 200:
            raise AuthenticationError(
                f"[HTTP:{response.status_code}] Could not authenticate at "
                + f"{url}: {response.text}"
            )

    def _check_order_status(self, order_url: str) -> str:
        """
        Back-end method called by `check_order_status` once or multiple times.

        :param order_url:
            URL of the placed order
        :returns:
            current order state (e.g., 'running', 'success', 'failed', etc.)
        """
        r = self.session.get(order_url)
        response = r.json()
        return response["state"]

    def check_order_status(
        self,
        order_url: str,
        loop: Optional[bool] = False,
        sleep_time: Optional[int] = 10,
        max_iter: Optional[int] = 1000,
    ):
        """
        Checks the order status of a placed order (authenticated session required).

        :param order_url:
            URL of the placed order
        :param loop:
            if False makes a single query about the order status (default). If True
            re-runs the query every xx seconds (10 by default) until a maximum of
            yy iterations (1000 by default) is reached or the order status is one
            of 'success', 'failed' or 'partial'
        :param sleep_time:
            time to sleep between repeated requests in seconds. Ignored if `loop`
            is False (default behavior)
        :param max_iter:
            maximum number of iterations in case of repeated requests. Ignored if
            `loop` is set to False.
        """
        if not loop:
            return self._check_order_status(order_url)

        with alive_bar(max_iter, force_tty=True) as prog_bar:
            for _ in range(max_iter):
                status = self._check_order_status(order_url)
                if status in ["success", "failed", "partial"]:
                    return status
                time.sleep(sleep_time)
                prog_bar()

        return status

    def place_order(
        self,
        order_name: str,
        product_bundle: Optional[str] = "analytic_8b_sr_udm2",
        processing_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Places (activates) an order. Only activated orders can be downloaded
        once they are available.

        IMPORTANT:
            To place an order you must have already queried the quick-search
            API to retrieve available item_ids!

        :param order_name:
            name of the order (will also appear in the online UI)
        :param product_bundle:
            product bundle to download. `analytic_8b_sr_udm2` (Super Dove
            with 8 bands, surface reflectance and quality mask) by default.
        :param processing_tools:
            optional list of pre-processing operators offered by Planet such
            as clipping image data to an Area of Interest.
            See this notebook for examples:
            https://github.com/planetlabs/notebooks/blob/master/jupyter-notebooks/orders/tools_and_toolchains.ipynb
        :returns:
            URL of the placed order
        """
        # set content-type to application/json
        headers = {"content-type": "application/json"}
        # prepare request body using (data part)
        data_request_dict = {}
        data_request_dict.update(
            {
                "item_type": self.request["item_types"][0],
                "item_ids": [x["id"] for x in self.features],
                "product_bundle": product_bundle,
            }
        )

        # create the order request
        order_request = {"name": order_name, "products": [data_request_dict]}
        # add further optional processing tools (clipping, band math, etc.)
        if processing_tools is not None:
            order_request.update({"tools": processing_tools})
        order_request_json = json.dumps(order_request)
        response = self.session.post(
            orders_url, data=order_request_json, headers=headers, auth=self.session.auth
        )

        if not response.ok:
            raise APIError(
                f"[HTTP:{response.status_code}]: Placing order failed: {response.content}"
            )

        # get order ID and return its URL
        order_id = response.json()["id"]
        order_url = orders_url + "/" + order_id
        return order_url

    def get_orders(self) -> pd.DataFrame:
        """
        Returns all available orders in a convenient `pandas.DataFrame`

        :returns:
            `DataFrame` with all orders available
        """
        response = self.session.get(orders_url)
        response.raise_for_status()
        orders = response.json()["orders"]
        return pd.DataFrame(orders)

    def download_order(
        self,
        download_dir: Path,
        order_name: Optional[str] = "",
        order_url: Optional[str] = "",
    ) -> None:
        """
        Download data from an order. Order must be activated!

        :param download_dir:
            directory where to download the Planet mapper to. Each scene is
            stored in a own sub-directory named by its ID to make the archive
            structure comparable to Sentinel-2 and the single assets (files)
            are placed within that sub-directory.
        :param order_name:
            name of the order to search for. Ignored if an `order_url` is provided
        :param order_url:
            URL of an order. If provided, `order_name` is ignored.
        """
        # get all available orders and search for the order name
        if order_url == "" and order_name == "":
            raise ValueError("Either order URL or name must be provided")
        # get order URL from its name if the URL is not provided
        if order_url == "":
            order_df = self.get_orders()
            order_rec = order_df[order_df.name == order_name].copy()
            if order_rec.empty:
                raise ValueError(f'Could not found a order named "{order_name}"')
            # extract the order URL
            order_url = list(order_rec["_links"].values[0].values())[0]

        # get URLs of the single assets (data sets) within the order
        r = self.session.get(order_url)
        response = r.json()
        results = response["_links"]["results"]
        results_urls = [r["location"] for r in results]

        # data handling stuff (file-naming) to prepar downloads
        results_folders = list()
        for f in results:
            # split paths
            a = f["name"].rsplit("/", 1)[1]
            # take the id part split it again and put together so we can extract the item id
            results_folders.append("_".join(a.split("_", 4)[:4]))

        # To construct the whole path, the file name is required
        results_names = list()
        for f in results:
            results_names.append(f["name"].rsplit("/", 1)[1])
        logger.info(f"{len(results_urls)} items to download from Planet")

        # actual downloading of data
        idx = 1
        n_results = len(results_urls) - 1  # -1 because we skip manifest.json
        for url, folder, name in zip(results_urls, results_folders, results_names):
            # skip manifest.json
            if name == "manifest.json":
                continue
            scene_dir = download_dir.joinpath(folder)
            scene_dir.mkdir(exist_ok=True)
            path = scene_dir.joinpath(name)
            r = requests.get(url, allow_redirects=True)
            open(path, "wb").write(r.content)
            logger.info(f"Downloaded Planet scene {name} to {path} ({idx}/{n_results})")
            idx += 1
