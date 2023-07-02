"""
Defines some static attributes of Landsat Collection 2 products.

Copyright (C) 2023 Lukas Valentin Graf

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

# available processing levels
class ProcessingLevels(Enum):  # noqa: F811
    L1 = "LEVEL1"
    L2 = "LEVEL2"


# Landsat processing levels as defined in the metadatabase
ProcessingLevelsDB = {"L1": "Level-1", "L2": "Level-2"}

# band mapping organized by sensor type
landsat_band_mapping = {
    "Multispectral_Scanner_System_L1-3": {
        "B4": "green",
        "B5": "red",
        "B6": "nir08",
        "B7": "nir09"},
    "Multispectral_Scanner_System_L4-5": {
        "B1": "green",
        "B2": "red",
        "B3": "nir08",
        "B4": "nir09"
    },
    "Thematic_Mapper": {
        "B1": "blue",
        "B2": "green",
        "B3": "red",
        "B4": "nir08",
        "B5": "swir16",
        "B6": "lwir",
        "B7": "swir22"},
    "Enhanced_Thematic_Mapper_Plus": {
        "B1": "blue",
        "B2": "green",
        "B3": "red",
        "B4": "nir08",
        "B5": "swir16",
        "B6": "lwir",
        "B7": "swir22"},
    "Operational_Land_Imager": {
        "B1": "coastal",
        "B2": "blue",
        "B3": "green",
        "B4": "red",
        "B5": "nir08",
        "B6": "swir16",
        "B7": "swir22",
        "B10": "lwir11"},
    "quality_flags": {
        "qa_pixel": "PIXEL",
        "qa_aerosol": "AEROSOL",
        "qa_radsat": "RADSAT",
        "qa": "QA",
        "cloud_qa": "cloud_qa"},
    "atmospheric_correction": {
        "cdist": "CDIST",
        "drad": "DRAD",
        "emis": "EMIS",
        "emsd": "EMSD",
        "lwir": "LWIR",
        "trad": "TRAD",
        "urad": "URAD",
        "atran": "ATRAN",
        "atmos_opacity": "OPACITY",
        "ang": "ANG"}
}

# TODO: L4 and L5 actually have two instruments (TM and MSS)
platform_sensor_mapping = {
    "LANDSAT_1": "Multispectral_Scanner_System_L1-3",
    "LANDSAT_2": "Multispectral_Scanner_System_L1-3",
    "LANDSAT_3": "Multispectral_Scanner_System_L1-3",
    "LANDSAT_4": "Thematic_Mapper",
    "LANDSAT_5": "Thematic_Mapper",
    "LANDSAT_7": "Enhanced_Thematic_Mapper_Plus",
    "LANDSAT_8": "Operational_Land_Imager",
    "LANDSAT_9": "Operational_Land_Imager"}

# spatial resolutions of the Landsat bands organized by sensor and product
# in meters
band_resolution = {
    "Multispectral_Scanner_System_L1-3": {
        "green": 80,
        "red": 80,
        "nir08": 80,
        "nir09": 80},
    "Multispectral_Scanner_System_L4-5": {
        "green": 80,
        "red": 80,
        "nir08": 80,
        "nir09": 80},
    "Thematic_Mapper": {
        "blue": 30,
        "green": 30,
        "red": 30,
        "nir08": 30,
        "swir16": 30,
        "lwir": 120,
        "swir22": 30},
    "Enhanced_Thematic_Mapper_Plus": {
        "blue": 30,
        "green": 30,
        "red": 30,
        "nir08": 30,
        "swir16": 30,
        "lwir": 60,
        "swir22": 30},
    "Operational_Land_Imager": {
        "coastal": 30,
        "blue": 30,
        "green": 30,
        "red": 30,
        "nir08": 30,
        "swir16": 30,
        "swir22": 30,
        "lwir11": 100},
    "quality_flags": {
        "qa_pixel": 30,
        "qa_aerosol": 30,
        "qa_radsat": 30,
        "qa": 30,
        "cloud_qa": 30},
    "atmospheric_correction": {
        "cdist": 30,
        "drad": 30,
        "emis": 30,
        "emsd": 30,
        "lwir": 30,
        "trad": 30,
        "urad": 30,
        "atran": 30,
        "atmos_opacity": 30,
        "ang": 30}
}
