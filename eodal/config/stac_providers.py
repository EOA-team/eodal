"""
List of STAC providers and their URLs and collection naming conventions

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
"""

from typing import List


class STAC_Providers:
    class AWS:
        """Amazon Web Services"""

        URL: str = "https://earth-search.aws.element84.com/v0"
        S2L1C: str = "sentinel-s2-l1c"
        S2L2A: str = "sentinel-s2-l2a"

        class Sentinel2:
            product_uri: str = "sentinel:product_id"
            scene_id: str = "id"
            platform: str = "platform"
            tile_id: List[str] = [
                "sentinel:utm_zone",
                "sentinel:latitude_band",
                "sentinel:grid_square",
            ]
            sensing_time: str = "datetime"
            sensing_time_fmt: str = "%Y-%m-%dT%H:%M:%SZ"
            cloud_cover: str = "eo:cloud_cover"
            epsg: str = "proj:epsg"

    class MSPC:
        """Microsoft Planetary Computer"""

        URL: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
        S2L1C: str = "sentinel-2-l1c"
        S2L2A: str = "sentinel-2-l2a"

        class Sentinel2:
            product_uri: str = "id"
            scene_id: str = "s2:granule_id"
            platform: str = "platform"
            tile_id: str = "s2:mgrs_tile"
            sensing_time: str = "datetime"
            sensing_time_fmt: str = "%Y-%m-%dT%H:%M:%S.%fZ"
            cloud_cover: str = "eo:cloud_cover"
            epsg: str = "proj:epsg"
