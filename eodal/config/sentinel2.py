"""
Global settings for Sentinel-2 that can be customized if required.

The ``Sentinel2`` class uses ``pydantic``. This means all attributes of the class can
be **overwritten** using environmental variables or a `.env` file.

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

from __future__ import annotations

from pydantic.main import BaseModel
from typing import List


class Sentinel2(BaseModel):
    """
    base class defining Sentinel-2 product, archive and sensor details
    """

    PROCESSING_LEVELS: List[str] = ["L1C", "L2A"]

    SPATIAL_RESOLUTIONS: dict = {
        60.0: ["B01", "B09", "B10"],
        10.0: ["B02", "B03", "B04", "B08"],
        20.0: ["B05", "B06", "B07", "B8A", "B11", "B12", "SCL"],
    }
    BAND_INDICES: dict = {
        "B01": 0,
        "B02": 1,
        "B03": 2,
        "B04": 3,
        "B05": 4,
        "B06": 5,
        "B07": 6,
        "B08": 7,
        "B8A": 8,
        "B09": 9,
        "B10": 10,
        "B11": 11,
        "B12": 12,
    }

    # define nodata values for ESA Sentinel-2 spectral bands (reflectance) and
    # scene classification layer (SCL)
    NODATA_REFLECTANCE: int = 64537
    NODATA_SCL: int = 254
