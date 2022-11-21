"""
A scene is a collection of raster bands with an acquisition date, an unique identifier
and a (remote sensing) platform that acquired the raster data.

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

import datetime
import numpy as np

from collections.abc import MutableMapping
from numbers import Number
from typing import Callable, List, Optional

from eodal.utils.constants import ProcessingLevels

class SceneProperties(object):
    """
    A class for storing scene-relevant properties

    :attribute acquisition_time:
        image acquisition time
    :attribute platform:
        name of the imaging platform
    :attribute sensor:
        name of the imaging sensor
    :attribute processing_level:
        processing level of the remotely sensed data (if
        known and applicable)
    :attribute product_uri:
        unique product (scene) identifier
    :attribute mode:
        imaging mode of SAR sensors
    """

    def __init__(
        self,
        acquisition_time: Optional[datetime.datetime] = datetime.datetime(2999, 1, 1),
        platform: Optional[str] = "",
        sensor: Optional[str] = "",
        processing_level: Optional[ProcessingLevels] = ProcessingLevels.UNKNOWN,
        product_uri: Optional[str] = "",
        mode: Optional[str] = ""
    ):
        """
        Class constructor

        :param acquisition_time:
            image acquisition time
        :param platform:
            name of the imaging platform
        :param sensor:
            name of the imaging sensor
        :param processing_level:
            processing level of the remotely sensed data (if
            known and applicable)
        :param product_uri:
            unique product (scene) identifier
        :attribute mode:
            imaging mode of SAR sensors
        """

        self.acquisition_time = acquisition_time
        self.platform = platform
        self.sensor = sensor
        self.processing_level = processing_level
        self.product_uri = product_uri
        self.mode = mode

    def __repr__(self) -> str:
        return str(self.__dict__)

    @property
    def acquisition_time(self) -> datetime.datetime:
        """acquisition time of the scene"""
        return self._acquisition_time

    @acquisition_time.setter
    def acquisition_time(self, time: datetime.datetime) -> None:
        """acquisition time of the scene"""
        if not isinstance(time, datetime.datetime):
            raise TypeError("Expected a datetime.datetime object")
        self._acquisition_time = time

    @property
    def platform(self) -> str:
        """name of the imaging platform"""
        return self._platform

    @platform.setter
    def platform(self, value: str) -> None:
        """name of the imaging plaform"""
        if not isinstance(value, str):
            raise TypeError("Expected a str object")
        self._platform = value

    @property
    def sensor(self) -> str:
        """name of the sensor"""
        return self._sensor

    @sensor.setter
    def sensor(self, value: str) -> None:
        """name of the sensor"""
        if not isinstance(value, str):
            raise TypeError("Expected a str object")
        self._sensor = value

    @property
    def processing_level(self) -> ProcessingLevels:
        """current processing level"""
        return self._processing_level

    @processing_level.setter
    def processing_level(self, value: ProcessingLevels):
        """current processing level"""
        self._processing_level = value

    @property
    def product_uri(self) -> str:
        """unique product (scene) identifier"""
        return self._product_uri

    @product_uri.setter
    def product_uri(self, value: str) -> None:
        """unique product (scene) identifier"""
        if not isinstance(value, str):
            raise TypeError("Expected a str object")
        self._product_uri = value

    @property
    def mode(self) -> str:
        """imaging mode of SAR sensors"""
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Expected a str object")
        self._mode = value


# class SceneCollection(MutableMapping):
#     """
#     Collection of 0:N scenes where each scene is a RasterCollection with
#     **non-empty** `SceneProperties` as each scene is indexed by its
#     acquistion time.
#     """
#     def __init__(
#         self,
#         scene_constructor: Optional[Callable[..., RasterCollection]] = None,
#         *args,
#         **kwargs
#     ):
#         """
#         Initializes a SceneCollection object with 0 to N scenes.
#
#          :param scene_constructor:
#             optional callable returning an `~eodal.core.raster.RasterCollection`
#             instance.
#         :param args:
#             arguments to pass to `scene_constructor` or one of RasterCollection's
#             class methods (e.g., `RasterCollection.from_multi_band_raster`)
#         :param kwargs:
#             key-word arguments to pass to `scene_constructor` or one of RasterCollection's
#             class methods (e.g., `RasterCollection.from_multi_band_raster`)
#         """
#         # mapper are stored in a dictionary like collection
#         self._frozen = False
#         self.collection = dict()
#         self._frozen = True
#
#         if scene_constructor is not None:
#             scene = scene_constructor.__call__(*args, **kwargs)
#             if not isinstance(scene, RasterCollection):
#                 raise TypeError('Only RasterCollection objects can be passed')
#             self.__setitem__(scene)
#
#     def __getitem__(self, key: str) -> RasterCollection:
#         return self.collection[key]
#
#     def __setitem__(self, item: RasterCollection):
#         if not isinstance(item, RasterCollection):
#             raise TypeError("Only RasterCollection objects can be passed")
#         key = item.scene_properties.acquisition_time
#         if key in self.collection.keys():
#             raise KeyError("Duplicate scene names are not permitted")
#         if key is None:
#             raise ValueError("RasterCollection passed must have an acquistion time stamp")
#         value = item.copy()
#         self.collection[key] = value
#
#     def __delitem__(self, key: str):
#         del self.collection[key]
#
#     def __iter__(self):
#         for k, v in self.collection.items():
#             yield k, v
#
#     def __len__(self) -> int:
#         return len(self.collection)
#
#     def __repr__(self) -> str:
#         pass
#
#     @property
#     def scene_names(self) -> List[str]:
#         """scene names in collection"""
#         return list(self.collection.keys())
#
#     def apply(self, func: Callable):
#         pass
#
#     def dump(self):
#         pass
#
#     def filter(self):
#         pass
#
#     def load(self):
#         pass
#
#     def plot(self):
#         pass
#
#     def to_xarray(self):
#         pass
