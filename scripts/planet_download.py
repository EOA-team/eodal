'''
Sample script showing how to use `EOdal` for downloading Planet-Scope data.

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
'''

from datetime import date
from eodal.config import get_settings
from eodal.downloader.planet_scope import PlanetAPIClient
from pathlib import Path

###################################
# usage example 1 - query archive by date and AOI, place order and download it once it's ready
start_date = date(2022,7,25)
end_date = date(2022,7,29)
bounding_box = Path('../data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp')
order_name = f'{date.today()}_ZH_Polygon_73129'
cloud_cover = 50.

# query the data API to get available mapper (no order placement, no download!)
# retrieves metadata, only
client = PlanetAPIClient.query_planet_api(
    start_date=start_date,
    end_date=end_date,
    bounding_box=bounding_box,
    cloud_cover_threshold=cloud_cover
)

# place the order based on the data found in the previous step
order_url = client.place_order(order_name=order_name)

# check the order status (it might take a while until the order is activated)
client.check_order_status(order_url, loop=True)

# download order -> make sure the order is activated (see previous step)
download_dir = Path('/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/__work__')
client.download_order(order_url, download_dir)

###################################
# usage example 2 - check placed orders
client = PlanetAPIClient()
# authenticate at the server -> the session attribute will be populated
client.authenticate(url=get_settings().ORDERS_URL)
# get all placed orders (pandas DataFrame)
order_df = client.get_orders()
