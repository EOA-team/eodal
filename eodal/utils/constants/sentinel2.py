"""
Defines some static attributes of Sentinel-2 MSI.

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

from enum import Enum
from eodal.utils.constants import ProcessingLevels


# available processing levels
class ProcessingLevels(Enum):
    L1C = "LEVEL1C"
    L2A = "LEVEL2A"


# Sentinel-2 processing levels as defined in the metadatabase
ProcessingLevelsDB = {"L1C": "Level-1C", "L2A": "Level-2A"}

# native spatial resolution of the S2 bands per processing level
band_resolution = {
    ProcessingLevels.L1C: {
        "B01": 60,
        "B02": 10,
        "B03": 10,
        "B04": 10,
        "B05": 20,
        "B06": 20,
        "B07": 20,
        "B08": 10,
        "B8A": 20,
        "B09": 60,
        "B10": 60,
        "B11": 20,
        "B12": 20,
    },
    ProcessingLevels.L2A: {
        "B01": 60,
        "B02": 10,
        "B03": 10,
        "B04": 10,
        "B05": 20,
        "B06": 20,
        "B07": 20,
        "B08": 10,
        "B8A": 20,
        "B09": 60,
        "B10": 60,
        "B11": 20,
        "B12": 20,
        "SCL": 20,
    },
}

# define central wavelengths of the single bands (nm) taken from
# https://sentinels.copernicus.eu/documents/247904/685211/S2-SRF_COPE-GSEG-EOPG-TN-15-0007_3.0.xlsx
# and refined for S2A and S2B using information from
# https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-2/instrument-payload/resolution-and-swath
central_wavelengths = {
    "S2A": {
        "B01": 442.7,
        "B02": 492.4,
        "B03": 559.8,
        "B04": 664.6,
        "B05": 704.1,
        "B06": 740.5,
        "B07": 782.8,
        "B08": 832.8,
        "B8A": 864.7,
        "B09": 945.1,
        "B10": 1373.5,
        "B11": 1613.7,
        "B12": 2202.4,
    },
    "S2B": {
        "B01": 442.2,
        "B02": 492.1,
        "B03": 559.0,
        "B04": 664.9,
        "B05": 703.8,
        "B06": 739.1,
        "B07": 779.7,
        "B08": 832.9,
        "B8A": 864.0,
        "B09": 943.2,
        "B10": 1376.9,
        "B11": 1610.4,
        "B12": 2185.7,
    },
    "unit": "nm",
}

band_widths = {
    "S2A": {
        "B01": 21,
        "B02": 66,
        "B03": 36,
        "B04": 31,
        "B05": 15,
        "B06": 15,
        "B07": 20,
        "B08": 106,
        "B8A": 21,
        "B09": 20,
        "B10": 31,
        "B11": 91,
        "B12": 175,
    },
    "S2B": {
        "B01": 21,
        "B02": 66,
        "B03": 36,
        "B04": 31,
        "B05": 16,
        "B06": 15,
        "B07": 20,
        "B08": 106,
        "B8A": 22,
        "B09": 21,
        "B10": 30,
        "B11": 94,
        "B12": 185,
    },
    "unit": "nm",
}

s2_band_mapping = {
    "B01": "ultra_blue",
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "red_edge_1",
    "B06": "red_edge_2",
    "B07": "red_edge_3",
    "B08": "nir_1",
    "B8A": "nir_2",
    "B09": "nir_3",
    "B11": "swir_1",
    "B12": "swir_2",
    "SCL": "scl",
}

# S2 data is stored as uint16, to convert to 0-1 reflectance factors
# apply this gain factor
s2_gain_factor = 0.0001


# scene classification layer (Sen2Cor)
class SCL_Classes(object):
    """
    class defining all possible SCL values and their meaning
    (SCL=Sentinel-2 scene classification)
    Class names follow the official ESA documentation available
    here:
    https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm
    (last access on 27.05.2021)
    """

    @classmethod
    def values(cls):
        values = {
            0: "no_data",
            1: "saturated_or_defective",
            2: "dark_area_pixels",
            3: "cloud_shadows",
            4: "vegetation",
            5: "non_vegetated",
            6: "water",
            7: "unclassified",
            8: "cloud_medium_probability",
            9: "cloud_high_probability",
            10: "thin_cirrus",
            11: "snow",
        }
        return values

    @classmethod
    def colors(cls):
        """
        Scene Classification Layer colors trying to mimic the default
        color map from ESA
        """
        scl_colors = [
            "black",  # nodata
            "red",  # saturated or defective
            "dimgrey",  # dark area pixels
            "chocolate",  # cloud shadows
            "yellowgreen",  # vegetation
            "yellow",  # bare soil
            "blue",  # open water
            "gray",  # unclassified
            "darkgrey",  # clouds medium probability
            "gainsboro",  # clouds high probability
            "mediumturquoise",  # thin cirrus
            "magenta",  # snow
        ]
        return scl_colors
