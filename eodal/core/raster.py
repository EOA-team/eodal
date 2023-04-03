"""
This module defines the ``RasterCollection`` class which is the basic class for reading, plotting,
transforming, manipulating and writing (geo-referenced) raster data in an intuitive, object-oriented
way (in terms of software philosophy).

A ``RasterCollection`` is collection of to zero to N `~eodal.core.band.Band` instances, where each
band denotes a two-dimensional array at its core. The ``RasterCollection`` class allows thereby
to handle ``Band`` instances with different spatial reference systems, spatial resolutions (i.e.,
grid cell sizes) and spatial extents.

Besides that, ``RasterCollection`` is a super class from which sensor-specific classes for reading
(satellite) raster image data inherit.

.. highlight:: python
.. code-block:: python

    import numpy as np
    from eodal.core.raster import RasterCollection
    from eodal.core.band import Band
    from eodal.core.band import GeoInfo

    # New collection from `numpy.ndarray`
    # Define GeoInfo and Array first and use them to initialize a new RasterCollection
    # instance:
    
    # provide EPSG code
    epsg = 32633
    # provide upper left (ul) x and y coordinate (in units of the coordinate system
    # given by the EPSG code defined above)
    ulx, uly = 300000, 5100000
    # provide pixel size (spatial resolution). Note that resolution in y direction is
    # negative because we start at the upper left corner
    pixres_x, pixres_y = 10, -10
    
    # get a new GeoInfo object
    geo_info = GeoInfo(epsg=epsg,ulx=ulx,uly=uly,pixres_x=pixres_x,pixres_y=pixres_y)
    
    # define a band name for the band data to add
    band_name = 'random'
    # optionally, you can also asign a `band_alias` (e.g., color name)
    band_alias = 'blue'
    
    # let's define some random numbers in a 2-d array
    values = np.random.random(size=(100,120))
    
    # get the RasterCollection object
    raster = RasterCollection(
             band_constructor=Band,
             band_name=band_name,
             values=values,
             band_alias=band_alias,
             geo_info=geo_info
    )

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

import datetime
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import rasterio as rio
import xarray as xr
import zarr

from collections.abc import MutableMapping
from copy import deepcopy
from functools import reduce
from itertools import chain
from matplotlib.axes import Axes
from matplotlib.pyplot import Figure
from numbers import Number
from pathlib import Path
from rasterio import band
from rasterio.drivers import driver_from_extension
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from eodal.config import get_settings
from eodal.core.band import Band
from eodal.core.operators import Operator
from eodal.core.spectral_indices import SpectralIndices
from eodal.utils.constants import ProcessingLevels
from eodal.utils.decorators import check_band_names
from eodal.utils.exceptions import BandNotFoundError

Settings = get_settings()


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
        acquisition_time: Optional[datetime.datetime | Number] = None,
        platform: Optional[str] = None,
        sensor: Optional[str] = None,
        processing_level: Optional[ProcessingLevels] = ProcessingLevels.UNKNOWN,
        product_uri: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        """
        Class constructor

        :param acquisition_time:
            image acquisition time. Can be a timestamp or any kind of numeric
            index.
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
    def acquisition_time(self, time: datetime.datetime | None) -> None:
        """acquisition time of the scene"""
        if time is not None:
            if not isinstance(time, datetime.datetime) and not isinstance(time, Number):
                raise TypeError("Expected a datetime.datetime or Number object")
            self._acquisition_time = time

    @property
    def platform(self) -> str | None:
        """name of the imaging platform"""
        return self._platform

    @platform.setter
    def platform(self, value: str | None) -> None:
        """name of the imaging plaform"""
        if value is not None:
            if not isinstance(value, str):
                raise TypeError("Expected a str object")
            self._platform = value

    @property
    def sensor(self) -> str | None:
        """name of the sensor"""
        return self._sensor

    @sensor.setter
    def sensor(self, value: str | None) -> None:
        """name of the sensor"""
        if value is not None:
            if not isinstance(value, str):
                raise TypeError("Expected a str object")
            self._sensor = value

    @property
    def processing_level(self) -> ProcessingLevels:
        """current processing level"""
        return self._processing_level

    @processing_level.setter
    def processing_level(self, value: ProcessingLevels | None) -> None:
        if value is not None:
            self._processing_level = value

    @property
    def product_uri(self) -> str | None:
        """unique product (scene) identifier"""
        return self._product_uri

    @product_uri.setter
    def product_uri(self, value: str | None) -> None:
        """unique product (scene) identifier"""
        if value is not None:
            if not isinstance(value, str):
                raise TypeError("Expected a str object")
            self._product_uri = value

    @property
    def mode(self) -> str | None:
        """imaging mode of SAR sensors"""
        return self._mode

    @mode.setter
    def mode(self, value: str | None) -> None:
        if value is not None:
            if not isinstance(value, str):
                raise TypeError("Expected a str object")
            self._mode = value

    def are_populated(self) -> bool:
        """
        returns a Boolean flag indicating if the class attributes
        have been populated with actual data or still equal defaults.

        A scene must have at least a time stamp.
        """
        return hasattr(self, "acquisition_time")


class RasterOperator(Operator):
    """
    Band operator supporting basic algebraic operations on
    `RasterCollection` objects
    """

    @classmethod
    def calc(
        cls,
        a,
        other: Band | Number | np.ndarray,
        operator: str,
        inplace: Optional[bool] = False,
        band_selection: Optional[List[str]] = None,
        right_sided: Optional[bool] = False,
    ) -> Union[None, np.ndarray]:
        """
        executes a custom algebraic operator on `RasterCollection` objects

        :param a:
            `RasterCollection` object with values (non-empty)
        :param other:
            `Band` object, scalar, 3-dimensional `numpy.array`, or RasterCollection to use
            on the right-hand side of the operator. If a `numpy.array` is passed the array
            must have either shape `(1,nrows,ncols)` or `(nband,nrows,ncols)`
            where `nrows` is the number of rows in `a`, ncols the number of columns
            in `a` and `nbands` the number of bands in a or the selection thereof.
            The latter method does *not* work if the bands in `a` selected differ
            in their shape.
        :param operator:
            symbolic representation of the operator (e.g., '+'
            for addition)
        :param inplace:
            returns a new `RasterCollection` object if False (default) otherwise
            overwrites the current `RasterCollection` data in `a`
        :param band_selection:
            optional selection of bands in `a` to which apply the operation
        :param right_sided:
            optional flag indicated that the order of `a` and `other` has to be
            switched. `False` by default. Set to `True` if the order of argument
            matters, i.e., for right-hand sided expression in case of subtraction,
            division and power.
        :returns:
            `numpy.ndarray` if inplace is False, None instead
        """
        cls.check_operator(operator=operator)
        # make a copy of a to avoid overwriting the original values
        _a = deepcopy(a)

        # if `other` is a Band object get its values
        if isinstance(other, Band):
            _other = deepcopy(other)
            _other = _other.values
        # check if `other` matches the shape
        elif isinstance(other, np.ndarray) or isinstance(other, np.ma.MaskedArray):
            # check if passed array is 2-d
            if len(other.shape) == 2:
                if other.shape != a.get_values(band_selection).shape[1::]:
                    raise ValueError(
                        f"Passed array has wrong number of rows and columns. "
                        + f"Expected {a.values.shape[1::]} - Got {other.shape}"
                    )
            # or 3-d
            elif len(other.shape) == 3:
                if other.shape != a.get_values(band_selection):
                    raise ValueError(
                        f"Passed array has wrong dimensions. Expected {a.values.shape}"
                        + f" - Got {other.shape}"
                    )
            # other dimensions are not allowed
            else:
                raise ValueError(
                    "Passed array must 2 or 3-dimensional. "
                    f"Got {len(other.shape)} dimensions instead"
                )
            _other = other.copy()
        elif isinstance(other, RasterCollection):
            _other = deepcopy(other)
            _other = other.get_values(band_selection=band_selection)
        elif isinstance(other, int) or isinstance(other, float):
            _other = other
        else:
            raise TypeError(f"{type(other)} is not supported")

        # perform the operation
        try:
            # mind the order which is important for some operators
            if right_sided:
                expr = f"_other {operator} _a.get_values(band_selection)"
            else:
                expr = f"_a.get_values(band_selection) {operator} _other"
            res = eval(expr)
        except Exception as e:
            raise cls.BandMathError(f"Could not execute {expr}: {e}")
        # return result or overwrite band data
        if band_selection is None:
            band_selection = a.band_names
        if not inplace:
            rcoll_out = RasterCollection()
        for idx, band_name in enumerate(band_selection):
            if inplace:
                object.__setattr__(a.collection[band_name], "values", res[idx, :, :])
            else:
                attrs = _a.collection[band_name].__dict__
                attrs.update({"values": res[idx, :, :]})
                rcoll_out.add_band(band_constructor=Band, **attrs)
        if not inplace:
            return rcoll_out


class RasterCollection(MutableMapping):
    """
    Basic class for storing and handling single and multi-band raster
    data from which sensor- or application-specific classes inherit.

    A ``RasterDataHandler`` contains zero to N instances of
    `~eodal.core.Band`. Bands are always indexed using their band
    name, therefore the band name must be **unique**!

    :attrib scene_properties:
        instance of `SceneProperties` for storing scene (i.e., dataset-wide)
        metadata. Designed for the usage with remote sensing data.
    :attrib band_names:
        names of the bands currently loaded into the collection
    :attrib band_aliases:
        optional aliases of the band names. Thus, a band can be accessed either
        by its name or its alias.
    :attrib empty:
        True if no bands are loaded into the collection, False if bands
        are available
    :attrib has_band_aliases:
        True if the band aliases are provided, False otherwise
    :attrib collection:
        dictionary-like collection of loaded raster ``Band`` instances
    """

    def __init__(
        self,
        band_constructor: Optional[Callable[..., Band]] = None,
        scene_properties: Optional[SceneProperties] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes a new `RasterCollection` with 0 up to n bands

        :param band_constructor:
            optional callable returning an `~eodal.core.Band`
            instance.
        :param scene_properties:
            optional scene properties of the dataset handled by the
            current ``RasterCollection`` instance
        :param args:
            arguments to pass to `band_constructor` or one of its
            class methods (`Band.from_rasterio`, `Band.from_vector`)
        :param kwargs:
            key-word arguments to pass to `band_constructor`  or one of its
            class methods (`Band.from_rasterio`, `Band.from_vector`)
        """

        if scene_properties is None:
            scene_properties = SceneProperties()
        if not isinstance(scene_properties, SceneProperties):
            raise TypeError(
                "scene_properties takes only objects " "of type SceneProperties"
            )
        self.scene_properties = scene_properties

        # bands are stored in a dictionary like collection
        self._frozen = False
        self.collection = dict()
        self._frozen = True

        self._band_aliases = []
        if band_constructor is not None:
            band = band_constructor.__call__(*args, **kwargs)
            if not isinstance(band, Band):
                raise TypeError("Only Band objects can be passed")
            self._band_aliases.append(band.band_alias)
            self.__setitem__(band)

    def __getitem__(self, key: str | slice) -> Band:
        def _get_band_from_key(key: str) -> Band:
            """
            helper function returning a Band object identified
            by its name from a RasterCollection
            """
            if key not in self.band_names:
                if key in self.band_aliases:
                    band_idx = self.band_aliases.index(key)
                    key = self.band_names[band_idx]
            return self.collection[key]

        # has a single key or slice been passed?
        if isinstance(key, str):
            try:
                return _get_band_from_key(key=key)
            except IndexError:
                raise BandNotFoundError(f"Could not find band {key}")

        elif isinstance(key, slice):
            # find the index of the start and the end of the slice
            slice_start = key.start
            slice_end = key.stop
            # return an empty RasterCollection if start and stop is the same
            # (numpy array behavior)
            if slice_start is None and slice_end is None:
                return RasterCollection()
            # if start is None use the first band name or its alias
            if slice_start is None:
                if slice_end in self.band_names:
                    slice_start = self.band_names[0]
                elif slice_end in self.band_aliases:
                    slice_start = self.band_aliases[0]
            # if end is None use the last band name or its alias
            end_increment = 0
            if slice_end is None:
                if slice_start in self.band_names:
                    slice_end = self.band_names[-1]
                elif slice_start in self.band_aliases:
                    slice_end = self.band_aliases[-1]
                # to ensure that the :: operator works, we need to make
                # sure the last band is also included in the slice
                end_increment = 1

            if set([slice_start, slice_end]).issubset(set(self.band_names)):
                idx_start = self.band_names.index(slice_start)
                idx_end = self.band_names.index(slice_end) + end_increment
                bands = self.band_names
            elif set([slice_start, slice_end]).issubset(set(self.band_aliases)):
                idx_start = self.band_aliases.index(slice_start)
                idx_end = self.band_aliases.index(slice_end) + end_increment
                bands = self.band_aliases
            else:
                raise BandNotFoundError(f"Could not find bands in {key}")
            slice_step = key.step
            if slice_step is None:
                slice_step = 1
            # get an empty RasterCollection for returing the slide
            out_raster = RasterCollection()
            for idx in range(idx_start, idx_end, slice_step):
                out_raster.add_band(_get_band_from_key(key=bands[idx]))
            return out_raster

    def __setitem__(self, item: Band):
        if not isinstance(item, Band):
            raise TypeError("Only Band objects can be passed")
        key = item.band_name
        if key in self.collection.keys():
            raise KeyError("Duplicate band names are not permitted")
        value = item.copy()
        self.collection[key] = value

    def __delitem__(self, key: str):
        del self.collection[key]

    def __iter__(self):
        for k, v in self.collection.items():
            yield k, v

    def __len__(self) -> int:
        return len(self.collection)

    def __add__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="+")

    def __radd__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="+")

    def __sub__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="-")

    def __rsub__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="-", right_sided=True)

    def __pow__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="**")

    def __rpow__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="**", right_sided=True)

    def __le__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="<=")

    def __rle__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="<=", right_sided=True)

    def __ge__(self, other):
        return RasterOperator.calc(a=self, other=other, operator=">=")

    def __rge__(self, other):
        return RasterOperator.calc(a=self, other=other, operator=">=", right_sided=True)

    def __truediv__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="/")

    def __rtruediv__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="/", right_sided=True)

    def __mul__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="*")

    def __rmul__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="*")

    def __ne__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="!=")

    def __rne__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="!=")

    def __eq__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="==")

    def __req__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="==")

    def __gt__(self, other):
        return RasterOperator.calc(a=self, other=other, operator=">")

    def __rgt__(self, other):
        return RasterOperator.calc(a=self, other=other, operator=">", right_sided=True)

    def __lt__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="<")

    def __rlt__(self, other):
        return RasterOperator.calc(a=self, other=other, operator="<", right_sided=True)

    def __repr__(self) -> str:
        if self.empty:
            return "Empty EOdal RasterCollection"
        else:
            return (
                f"EOdal RasterCollection\n----------------------\n"
                + f'# Bands:    {len(self)}\nBand names:    {", ".join(self.band_names)}\n'
                + f'Band aliases:    {", ".join(self.band_aliases)}'
            )

    @property
    def band_names(self) -> List[str]:
        """band names in collection"""
        return list(self.collection.keys())

    @property
    def band_aliases(self) -> List[str]:
        """band aliases in collection"""
        return self._band_aliases

    @property
    def empty(self) -> bool:
        """Handler has bands loaded"""
        return len(self.collection) == 0

    @property
    def collection(self) -> MutableMapping:
        """collection of the bands currently loaded"""
        return self._collection

    @collection.setter
    def collection(self, value):
        """collection of the bands currently loaded"""
        if not isinstance(value, dict):
            raise TypeError("Only dictionaries can be passed")
        if self._frozen:
            raise ValueError("Existing collections cannot be overwritten")
        if not self._frozen:
            self._collection = value

    @property
    def has_band_aliases(self) -> bool:
        """collection supports aliasing"""
        return len(self.band_aliases) > 0

    @property
    def is_scene(self) -> bool:
        """is the RasterCollection a scene"""
        return self.scene_properties.are_populated()

    @check_band_names
    def get_band_alias(self, band_name: str) -> Union[Dict[str, str], None]:
        """
        Retuns the band_name-alias mapper of a given band
        in collection if the band has an alias, None instead

        :param band_name:
            name of the band for which to return the alias or
            its name if the alias is provided
        :returns:
            mapping of band_name:band_alias (band name is always the
            key and band_alias is the value)
        """
        if self[band_name].has_alias:
            idx = self.band_names.index(band_name)
            band_alias = self.band_aliases[idx]
            return {band_name: band_alias}

    @staticmethod
    def _bands_from_selection(
        fpath_raster: Path | Dict,
        band_idxs: Optional[List[int]] = None,
        band_names_src: Optional[List[str]] = None,
        band_names_dst: Optional[List[str]] = None,
    ) -> Dict[str, Union[str, int]]:
        """
        Selects bands in a multi-band raster dataset based on a custom
        selection of band indices or band names.

        .. versionadd:: 0.2.0
            works also with a dictionary of hrefs returned from a
            STAC query

        :param fpath_raster:
            file-path to the raster file (technically spoken, this
            can also have just a single band) **or** when `USE_STAC` is True
            the `assets` dictionary returned from a STAC call.
        :param band_idxs:
            optional list of band indices in the raster dataset
            to read. If not provided (default) all bands are loaded.
            Ignored if `band_names_src` is provided.
        :param band_names_src:
            optional list of band names in the raster dataset to
            read. If not provided (default) all bands are loaded. If
            `band_idxs` and `band_names_src` are provided, the former
            is ignored.
        :param band_names_dst:
            optional list of band names in the resulting collection.
            Must match the length and order of `band_idxs` or
            `band_names_src`
        :returns:
            dictionary with band indices, and names based on the custom
            selection
        """
        # check band selection
        band_names, band_count = None, None
        if band_idxs is None:
            if isinstance(fpath_raster, dict):
                band_names = list(fpath_raster.keys())
                band_count = len(band_names)
            else:
                try:
                    with rio.open(fpath_raster, "r") as src:
                        band_names = list(src.descriptions)
                        band_count = src.count
                except Exception as e:
                    raise IOError(f"Could not read {fpath_raster}: {e}")
            # use default band names if not provided in data set
            if len(band_names) == 0:
                band_names_src = [f"B{idx+1}" for idx in range(band_count)]
            else:
                if band_names_src is None:
                    band_names_src = band_names
            # is a selection of bands provided? If no use all available bands
            # otherwise check the band indices
            if band_names_src is None or set(band_names_src) == {None}:
                # get band indices of all bands, add 1 since GDAL starts
                # counting at 1
                band_idxs = [x + 1 for x in range(band_count)]
            else:
                # get band indices of selected bands (+1 because of GDAL)
                band_idxs = [
                    band_names.index(x) + 1 for x in band_names_src if x in band_names
                ]

        band_count = len(band_idxs)
        # make sure neither band_idxs nor band_names_src is None or empty
        if band_idxs is None or len(band_idxs) == 0:
            raise ValueError("No band indices could be determined")

        # make sure band_names_src are set
        if band_names_src is None or set(band_names_src) == {None}:
            band_names_src = [f"B{idx+1}" for idx in range(band_count)]

        # set band_names_dst to values of band_names_src or default names
        if band_names_dst is None or set(band_names_src) == {None}:
            band_names_dst = band_names_src

        return {
            "band_idxs": band_idxs,
            "band_names_src": band_names_src,
            "band_names_dst": band_names_dst,
            "band_count": band_count,
        }

    def apply(self, func: Callable, *args, **kwargs) -> Any:
        """
        Apply a custom function to a ``RasterCollection``.

        :param func:
            custom callable taking the ``RasterCollection`` as first
            argument
        :param args:
            optional arguments to pass to `func`
        :param kwargs:
            optional keyword arguments to pass to `func`
        :returns:
            results of `func`
        """
        try:
            return func.__call__(self, *args, **kwargs)
        except Exception as e:
            raise ValueError from e

    def copy(self):
        """
        Returns a copy of the current ``RasterCollection``
        """
        return deepcopy(self)

    @classmethod
    def from_multi_band_raster(
        cls,
        fpath_raster: Path,
        band_idxs: Optional[List[int]] = None,
        band_names_src: Optional[List[str]] = None,
        band_names_dst: Optional[List[str]] = None,
        band_aliases: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Loads bands from a multi-band raster file into a new
        `RasterCollection` instance.

        Wrapper around `~eodal.core.Band.from_rasterio` for
        1 to N raster bands.

        :param fpath_raster:
            file-path to the raster file (technically spoken, this
            can also have just a single band)
        :param band_idxs:
            optional list of band indices in the raster dataset
            to read. If not provided (default) all bands are loaded.
            Ignored if `band_names_src` is provided.
        :param band_names_src:
            optional list of band names in the raster dataset to
            read. If not provided (default) all bands are loaded. If
            `band_idxs` and `band_names_src` are provided, the former
            is ignored.
        :param band_names_dst:
            optional list of band names in the resulting collection.
            Must match the length and order of `band_idxs` or
            `band_names_src`
        :param band_aliases:
            optional list of aliases to use for *aliasing* of band names
        :param kwargs:
            optional key-word arguments accepted by
            `~eodal.core.Band.from_rasterio`
        :returns:
            `RasterCollection` instance with loaded bands from the
            input raster data set.
        """
        # check band selection
        band_props = cls._bands_from_selection(
            fpath_raster=fpath_raster,
            band_idxs=band_idxs,
            band_names_src=band_names_src,
            band_names_dst=band_names_dst,
        )

        # make sure band aliases match the length of bands
        if band_aliases is not None:
            if len(band_aliases) != band_props["band_count"]:
                raise ValueError(
                    f"Number of band_aliases ({len(band_aliases)}) does "
                    f'not match number of bands to load ({band_props["band_count"]})'
                )
        else:
            band_aliases = ["" for _ in range(band_props["band_count"])]

        # loop over the bands and add them to an empty handler
        handler = cls()
        for band_idx in range(band_props["band_count"]):
            try:
                handler.add_band(
                    Band.from_rasterio,
                    fpath_raster=fpath_raster,
                    band_idx=band_props["band_idxs"][band_idx],
                    band_name_dst=band_props["band_names_dst"][band_idx],
                    band_alias=band_aliases[band_idx],
                    **kwargs,
                )
            except Exception as e:
                raise Exception(
                    f"Could not add band {band_names_src[band_idx]} "
                    f"from {fpath_raster} to handler: {e}"
                )
        return handler

    @classmethod
    def read_pixels(
        cls,
        fpath_raster: Path,
        vector_features: Union[Path, gpd.GeoDataFrame],
        band_idxs: List[Optional[int]] = None,
        band_names_src: List[Optional[str]] = None,
        band_names_dst: List[Optional[str]] = None,
    ) -> gpd.GeoDataFrame:
        """
        Wrapper around `~eodal.core.band.read_pixels` for raster datasets
        with multiple bands

        NOTE:
            The pixels to read are defined by a ``GeoDataFrame`` or file with
            vector features understood by ``fiona``. If the geometry type is not
            ``Point`` the centroids will be used for extracting the closest
            grid cell value.

        :param fpath_raster:
            file-path to the raster dataset from which to extract pixel values
        :param vector_features:
            file-path or ``GeoDataFrame`` to features defining the pixels to read
            from a raster dataset. The geometries can be of type ``Point``,
            ``Polygon`` or ``MultiPolygon``. In the latter two cases the centroids
            are used to extract pixel values, whereas for point features the
            closest raster grid cell is selected.
        ::param band_idxs:
            optional list of band indices in the raster dataset to read. If not
            provided (default) all bands are loaded. Ignored if `band_names_src` is
            provided.
        :param band_names_src:
            optional list of band names in the raster dataset to read. If not provided
            (default) all bands are loaded. If `band_idxs` and `band_names_src` are
            provided, the former is ignored.
        :param band_names_dst:
            optional list of band names in the resulting collection.Must match the length
            and order of `band_idxs` or `band_names_src`.
        :returns:
            ``GeoDataFrame`` with extracted pixel values. If the vector features
            defining the sampling points are not within the spatial extent of the
            raster dataset the pixel values are set to nodata (inferred from
            the raster source)
        """
        # check band selection
        band_props = cls._bands_from_selection(
            fpath_raster=fpath_raster,
            band_idxs=band_idxs,
            band_names_src=band_names_src,
            band_names_dst=band_names_dst,
        )

        # loop over bands and extract values from raster dataset
        for idx in range(band_props["band_count"]):
            if idx == 0:
                gdf = Band.read_pixels(
                    fpath_raster=fpath_raster,
                    vector_features=vector_features,
                    band_idx=band_props["band_idxs"][idx],
                    band_name_src=band_props["band_names_src"][idx],
                    band_name_dst=band_props["band_names_dst"][idx],
                )
            else:
                gdf = Band.read_pixels(
                    fpath_raster=fpath_raster,
                    vector_features=gdf,
                    band_idx=band_props["band_idxs"][idx],
                    band_name_src=band_props["band_names_src"][idx],
                    band_name_dst=band_props["band_names_dst"][idx],
                )

        return gdf

    @check_band_names
    def drop_band(self, band_name: str):
        """
        Deletes a band from the current collection

        :param band_name:
            name of the band to drop
        """
        # ensure band aliases get deleted as well
        if self.has_band_aliases:
            if self[band_name].alias in self.band_aliases:
                self._band_aliases.remove(self[band_name].alias)
        self.__delitem__(band_name)

    def is_bandstack(
        self, band_selection: Optional[List[str]] = None
    ) -> Union[bool, None]:
        """
        Checks if the rasters handled in the collection fulfill the bandstack
        criteria.

        These criteria are:
            - all bands have the same CRS
            - all bands have the same x and y dimension (number of rows and columns)
            - all bands must have the same upper left corner coordinates

        :param band_selection:
            if not None, checks only a list of selected bands. By default,
            all bands of the current object are checked.
        :returns:
            True if the current object fulfills the criteria else False;
            None if no bands are loaded into the handler's collection.
        """
        if band_selection is None:
            band_selection = self.band_names

        # return None if no bands are in collection
        if self.empty:
            return None

        # otherwise use the first band (that will then always exist)
        # as reference to check the other bands (if any) against
        first_geo_info = self[band_selection[0]].geo_info
        first_shape = (self[band_selection[0]].nrows, self[band_selection[0]].ncols)
        for idx in range(1, len(band_selection)):
            this_geo_info = self[band_selection[idx]].geo_info
            this_shape = (
                self[band_selection[idx]].nrows,
                self[band_selection[idx]].ncols,
            )
            if this_shape != first_shape:
                return False
            if this_geo_info.epsg != first_geo_info.epsg:
                return False
            if this_geo_info.ulx != first_geo_info.ulx:
                return False
            if this_geo_info.uly != first_geo_info.uly:
                return False
            if this_geo_info.pixres_x != first_geo_info.pixres_x:
                return False
            if this_geo_info.pixres_y != first_geo_info.pixres_y:
                return False

        return True

    def add_band(
        self, band_constructor: Union[Callable[..., Band], Band], *args, **kwargs
    ) -> None:
        """
        Adds a band to the collection of raster bands.

        Raises an error if a band with the same name already exists (unique
        name constraint)

        :param band_constructor:
            callable returning a `~eodal.core.Band` instance or existing
            `Band` instance
        :param args:
            arguments to pass to `band_constructor` or one of its
            class methods (`Band.from_rasterio`, `Band.from_vector`)
        :param kwargs:
            key-word arguments to pass to `band_constructor`  or one of its
            class methods (`Band.from_rasterio`, `Band.from_vector`)
        """
        try:
            if isinstance(band_constructor, Band):
                band = band_constructor
            else:
                band = band_constructor.__call__(*args, **kwargs)
        except Exception as e:
            raise ValueError(f"Cannot initialize new Band instance: {e}")

        try:
            self.__setitem__(band)
            # forward band alias if any
            if band.has_alias:
                self._band_aliases.append(band.band_alias)
        except Exception as e:
            raise KeyError(f"Cannot add raster band: {e}")

    @check_band_names
    def clip_bands(
        self,
        band_selection: Optional[List[str]] = None,
        inplace: Optional[bool] = False,
        **kwargs,
    ):
        """
        Clip bands in RasterCollection to a user-defined spatial bounds.

        :param band_selection:
            optional list of bands to clip. If not provided takes all available
            bands.
        :param inplace:
            if False (default) returns a copy of the ``RasterCollection`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :param **kwargs:
            key-word arguments to pass to `Band.clip` method.
        """
        if band_selection is None:
            band_selection = self.band_names
        # loop over bands and try to subset them spatially
        # initialize a new raster collection if inplace is False
        collection = None
        if inplace:
            kwargs.update({"inplace": True})
        if not inplace:
            attrs = deepcopy(self.__dict__)
            attrs.pop("_collection")
            collection = RasterCollection(**attrs)

        # loop over band reproject the selected ones
        for band_name in band_selection:
            if inplace:
                self.collection[band_name].clip(**kwargs)
            else:
                band = self.get_band(band_name)
                collection.add_band(band_constructor=band.clip, **kwargs)

        if not inplace:
            return collection

    @check_band_names
    def plot_band(self, band_name: str, **kwargs) -> Figure:
        """
        Plots a band in the collection of raster bands.

        Wrapper method around `~eodal.core.Band.plot`.

        :param band_name:
            name of the band to plot. Aliasing is supported.
        :param kwargs:
            key-word arguments to pass to `~eodal.core.Band.plot`
        :returns:
            `~matplotlib.pyplot.Figure` with band plotted as map
        """
        return self[band_name].plot(**kwargs)

    @check_band_names
    def plot_multiple_bands(
        self,
        band_selection: Optional[List[str]] = None,
        ax: Optional[Axes] = None,
        **kwargs,
    ):
        """
        Plots three selected bands in a pseudo RGB with 8bit color-depth.

        IMPORTANT:
            The bands to plot **must** have the same spatial resolution,
            extent and CRS

        :param band_selection:
            optional list of bands to plot. If not provided takes the
            first three bands (or less) to plot
        :param ax:
            optional `matplotlib.axes` object to plot onto
        :returns:
            `~matplotlib.pyplot.Figure` with band plotted as map in
            8bit color depth
        """
        # check passed band_selection
        if band_selection is None:
            band_selection = self.band_names
        # if one band was passed only call plot band
        if len(band_selection) == 1:
            return self.plot_band(band_name=band_selection[0], **kwargs)

        # if too many bands are passed take the first three
        if len(band_selection) > 3:
            band_selection = band_selection[0:3]
        # but raise an error when less than three bands are available
        # unless it's
        elif len(band_selection) < 3:
            raise ValueError("Need three bands to plot")

        # check if data can be stacked
        if not self.is_bandstack(band_selection):
            raise ValueError(
                "Bands to plot must share same spatial extent, pixel size and CRS"
            )

        # get bounds in the spatial coordinate system for plotting
        xmin, ymin, xmax, ymax = self[band_selection[0]].bounds.exterior.bounds
        # determine intervals for plotting and aspect ratio (figsize)
        east_west_dim = xmax - xmin
        if abs(east_west_dim) < 5000:
            x_interval = 500
        elif abs(east_west_dim) >= 5000 and abs(east_west_dim) < 100000:
            x_interval = 5000
        else:
            x_interval = 50000
        north_south_dim = ymax - ymin
        if abs(north_south_dim) < 5000:
            y_interval = 500
        elif abs(north_south_dim) >= 5000 and abs(north_south_dim) < 100000:
            y_interval = 5000
        else:
            y_interval = 50000

        # clip values to 8bit color depth
        array_list = []
        masked = []
        for band_name in band_selection:
            band_data = self.get_band(band_name).values
            new_arr = (
                (band_data - band_data.min())
                * (1 / (band_data.max() - band_data.min()) * 255)
            ).astype("uint8")
            array_list.append(new_arr)
            masked.append(isinstance(new_arr, np.ma.MaskedArray))
        # stack arrays into 3d array
        if np.array(masked).any():
            stack = np.ma.dstack(array_list)
            # set masked values to zero reflectance
            stack.data[stack.mask] = 0
            stack = stack.data
        else:
            stack = np.dstack(array_list)
        # get quantiles to improve plot visibility
        vmin = np.nanquantile(stack, 0.1)
        vmax = np.nanquantile(stack, 0.9)

        # get new axis and figure or figure from existing axis
        if ax is None:
            fig = plt.figure(**kwargs)
            ax = fig.add_subplot(111)
        else:
            fig = ax.get_figure()
        ax.imshow(stack, vmin=vmin, vmax=vmax, extent=[xmin, xmax, ymin, ymax])
        # set axis labels
        epsg = self[band_selection[0]].geo_info.epsg
        if self[band_selection[0]].crs.is_geographic:
            unit = "deg"
        elif self[band_selection[0]].crs.is_projected:
            unit = "m"
        fontsize = kwargs.get("fontsize", 12)
        ax.set_xlabel(f"X [{unit}] (EPSG:{epsg})", fontsize=fontsize)
        ax.xaxis.set_ticks(np.arange(xmin, xmax, x_interval))
        ax.set_ylabel(f"Y [{unit}] (EPSG:{epsg})", fontsize=fontsize)
        ax.yaxis.set_ticks(np.arange(ymin, ymax, y_interval))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        # add title str
        title_str = ", ".join(band_selection)
        ax.set_title(title_str, fontdict={"fontsize": fontsize})
        return fig

    @check_band_names
    def get_band(self, band_name: str) -> Union[Band, None]:
        """
        Returns a single band from the collection or None
        if the band is not found.

        :param band_name:
            band name (or its alias) to return
        :returns:
            ``Band`` instance from band name
        """
        return self.collection.get(band_name, None)

    # @check_band_names
    def get_pixels(
        self,
        vector_features: Union[Path, gpd.GeoDataFrame],
        band_selection: Optional[List[str]] = None,
    ) -> gpd.GeoDataFrame:
        """
        Returns pixel values from bands in the collection as ``GeoDataFrame``.

        Since a pixel is a dimensionless object (``Point``) the extraction
        method works for raster bands with different pixel sizes, spatial
        extent and coordinate systems. If a pixel cannot be extracted from a
        raster band, the band's nodata value is inserted.

        :param band_selection:
            optional selection of bands to return
        :param vector_features:
            file-path or ``GeoDataFrame`` to features defining the pixels to read
            from the raster bands selected. The geometries can be of type ``Point``,
            ``Polygon`` or ``MultiPolygon``. In the latter two cases the centroids
            are used to extract pixel values, whereas for point features the
            closest raster grid cell is selected.
        :returns:
            ``GeoDataFrame`` with extracted raster values per pixel or
            Polygon centroid.
        """
        if band_selection is None:
            band_selection = self.band_names

        # loop over bands and extract the raster values into a GeoDataFrame
        for idx, band_name in enumerate(band_selection):
            # open a new GeoDataFrame for the first band and re-use it for
            # the other bands. This way we do not have to merge the single
            # GeoDataFrames afterwards
            if idx == 0:
                gdf = self[band_name].get_pixels(vector_features=vector_features)
            else:
                gdf = self[band_name].get_pixels(vector_features=gdf)

        return gdf

    @check_band_names
    def get_values(
        self, band_selection: Optional[List[str]] = None
    ) -> Union[np.ma.MaskedArray, np.ndarray]:
        """
        Returns raster values as stacked array in collection.

        NOTE:
            The selection of bands to return as stacked array
            **must** share the same spatial extent, pixel size
            and coordinate system

        :param band_selection:
            optional selection of bands to return
        :returns:
            raster band values in their underlying storage
            type (``numpy.ndarray``, ``numpy.ma.MaskedArray``,
            ``zarr``)
        """
        if band_selection is None:
            band_selection = self.band_names

        # check if the selected bands have the same spatial extent, pixel
        # cell size and spatial coordinate system (if not stacking fails)
        if not self.is_bandstack(band_selection):
            raise ValueError(
                "Cannot stack raster bands - they do not align spatially "
                "to each other.\nConsider reprojection/ resampling first."
            )

        stack_bands = [self.get_band(x).values for x in band_selection]
        array_types = [type(x) for x in stack_bands]

        # stack arrays along first axis
        # we need np.ma in case the array is a masked array
        if set(array_types) == {np.ma.MaskedArray}:
            return np.ma.stack(stack_bands, axis=0)
        elif set(array_types) == {np.ndarray}:
            return np.stack(stack_bands, axis=0)
        elif set(array_types) == {np.ma.MaskedArray, np.ndarray}:
            return np.ma.stack(stack_bands, axis=0)
        elif set(array_types) == {zarr.core.Array}:
            raise NotImplementedError()
        else:
            raise ValueError("Unsupported array type")

    @check_band_names
    def band_summaries(
        self, band_selection: Optional[List[str]] = None, **kwargs
    ) -> gpd.GeoDataFrame:
        """
        Descriptive band statistics by calling `Band.reduce` for bands in a collection.

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :param kwargs:
            optional keyword arguments to pass to `~eodal.core.band.Band.reduce`. Use
            `by` to get descriptive statistics by selected geometry features (e.g.,
            single polygons).
        :returns:
            ``GeoDataFrame`` with descriptive statistics for all bands selected and geometry
            features passed (optional)
        """
        stats = []
        if band_selection is None:
            band_selection = self.band_names
        for band_name in band_selection:
            band_stats = self[band_name].reduce(**kwargs)
            # band_stats is a list of 1:N entries (one per feature on which reduce
            # was called); we add the band name as attribute
            for idx in range(len(band_stats)):
                band_stats[idx].update({"band_name": band_name})
            stats.append(band_stats)
        # since the geometry information was passed on, a GeoDataFrame can be returned
        df = pd.DataFrame(list(chain(*stats)))
        # check if the returned DataFrame is empty. In this case return an empty
        # GeoDataFrame
        if df.empty:
            return gpd.GeoDataFrame()

        gdf = gpd.GeoDataFrame(df, geometry=df["geometry"], crs=df["crs"].iloc[0])
        # cast columns to float; otherwise pandas throws an error:
        # TypeError: unhashable type: 'MaskedConstant'
        methods = kwargs.get("method", ["min", "mean", "std", "max", "count"])
        # check if method contains callable functions
        cleaned_methods = []
        for method in methods:
            if callable(method):
                cleaned_methods.append(method.__name__)
            else:
                cleaned_methods.append(method)
        gdf[cleaned_methods] = gdf[cleaned_methods].astype(float)
        gdf.drop(columns=["crs"], inplace=True)
        return gdf

    @check_band_names
    def reproject(
        self,
        band_selection: Optional[List[str]] = None,
        inplace: Optional[bool] = False,
        **kwargs,
    ):
        """
        Reprojects band in the collection from one coordinate system
        into another

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :param inplace:
            if False returns a new `RasterCollection` (default) otherwise
            overwrites existing raster band entries
        :param kwargs:
            key-word arguments to pass to `~eodal.core.Band.reproject`
        :returns:
            new RasterCollection if `inplace==False`, None otherwise
        """
        if band_selection is None:
            band_selection = self.band_names
        # initialize a new raster collection if inplace is False
        collection = None
        if inplace:
            kwargs.update({"inplace": True})
        else:
            attrs = deepcopy(self.__dict__)
            attrs.pop("_collection")
            collection = RasterCollection(**attrs)

        # loop over band reproject the selected ones
        for band_name in band_selection:
            if inplace:
                self.collection[band_name].reproject(**kwargs)
            else:
                band = self.get_band(band_name)
                collection.add_band(band_constructor=band.reproject, **kwargs)

        if not inplace:
            return collection

    @check_band_names
    def resample(
        self,
        band_selection: Optional[List[str]] = None,
        inplace: Optional[bool] = False,
        **kwargs,
    ):
        """
        Resamples band in the collection into a different spatial resolution

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :param inplace:
            if False returns a new `RasterCollection` (default) otherwise
            overwrites existing raster band entries
        :param kwargs:
            key-word arguments to pass to `~eodal.core.Band.resample`
        :returns:
            new RasterCollection if `inplace==False`, None otherwise
        """
        if band_selection is None:
            band_selection = self.band_names
        # initialize a new raster collection if inplace is False
        collection = None
        if inplace:
            kwargs.update({"inplace": True})
        else:
            attrs = deepcopy(self.__dict__)
            attrs.pop("_collection")
            collection = RasterCollection(**attrs)

        # loop over band reproject the selected ones
        for band_name in band_selection:
            if inplace:
                self.collection[band_name].resample(**kwargs)
            else:
                band = self.get_band(band_name)
                collection.add_band(band_constructor=band.resample, **kwargs)

        return collection

    def mask(
        self,
        mask: Union[str, np.ndarray, Band],
        mask_values: Optional[List[Any]] = None,
        keep_mask_values: Optional[bool] = False,
        bands_to_mask: Optional[List[str]] = None,
        inplace: Optional[bool] = False,
    ):
        """
        Masks pixels of bands in the collection using a boolean array.

        IMPORTANT:
            The mask band (or mask array) and the bands to mask **must**
            have the same shape!

        :param mask:
            either a band out of the collection (identified through its
            band name) or a ``numpy.ndarray`` of datatype boolean or
            another `Band` object
        :param mask_values:
            if `mask` is a band out of the collection, a list of values
            **must** be specified to create a boolean mask. Ignored if `mask`
            is already a boolean ``numpy.ndarray``
        :param keep_mask_values:
            if False (default), pixels in `mask` corresponding to `mask_values`
            are masked, otherwise all other pixel values are masked.
            Ignored if `mask` is already a boolean ``numpy.ndarray``.
        :param bands_to_mask:
            bands in the collection to mask based on `mask`. If not provided,
            all bands are masked
        :param inplace:
            if False returns a new `RasterCollection` (default) otherwise
            overwrites existing raster band entries
        :returns:
            new RasterCollection if `inplace==False`, None otherwise
        """
        _mask = deepcopy(mask)
        # check mask and prepare it if required
        if isinstance(_mask, np.ndarray):
            if mask.dtype != "bool":
                raise TypeError("When providing an array it must be boolean")
            if len(_mask.shape) != 2:
                raise ValueError("When providing an array it must be 2-dimensional")
        elif isinstance(_mask, str):
            try:
                _mask = self.get_values(band_selection=[_mask])[0, :, :]
            except Exception as e:
                raise ValueError(f"Invalid mask band: {e}")
            # translate mask band into boolean array
            if mask_values is None:
                raise ValueError(
                    "When using a band as mask, you have to provide a list of mask values"
                )
            # convert the mask to a temporary binary mask
            tmp = np.zeros_like(_mask)
            # set valid classes to 1, the other ones are zero
            if keep_mask_values:
                # drop all other values not in mask_values
                tmp[~np.isin(_mask, mask_values)] = 1
            else:
                # drop all values in mask_values
                tmp[np.isin(_mask, mask_values)] = 1
            _mask = tmp.astype("bool")
        elif isinstance(_mask, Band):
            if _mask.values.dtype != "bool":
                raise TypeError(
                    f"Mask must have boolean values not {_mask.values.dtype}"
                )
            _mask = _mask.values
        else:
            raise TypeError(
                f"Mask must be either band_name or np.ndarray not {type(_mask)}"
            )

        # check bands to mask
        if bands_to_mask is None:
            bands_to_mask = self.band_names

        # check shapes of bands and mask before applying the mask
        if not self.is_bandstack(band_selection=bands_to_mask):
            raise ValueError(
                "Can only mask bands that have the same spatial extent, pixel size and CRS"
            )

        # initialize a new raster collection if inplace is False
        collection = None
        if not inplace:
            attrs = deepcopy(self.__dict__)
            attrs.pop("_collection")
            collection = RasterCollection(**attrs)

        # loop over band reproject the selected ones
        for band_name in bands_to_mask:
            if inplace:
                self[band_name].mask(mask=_mask, inplace=inplace)
            else:
                band = self.get_band(band_name)
                collection.add_band(
                    band_constructor=band.mask, mask=_mask, inplace=inplace
                )

        return collection

    @check_band_names
    def scale(
        self,
        band_selection: Optional[List[str]] = None,
        inplace: Optional[bool] = False,
        **kwargs,
    ):
        """
        Applies gain and offset factors to bands in collection

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :param inplace:
            if False returns a new `RasterCollection` (default) otherwise
            overwrites existing raster band entries
        :param kwargs:
            optional kwargs to pass to `~eodal.core.band.Band.scale_data`
        :returns:
            `RasterCollection` if `inplace == False`, None otherwise
        """
        if band_selection is None:
            band_selection = self.band_names

        # initialize a new raster collection if inplace is False
        collection = None
        if not inplace:
            attrs = deepcopy(self.__dict__)
            attrs.pop("_collection")
            collection = RasterCollection(**attrs)

        # loop over band reproject the selected ones
        for band_name in band_selection:
            if inplace:
                self.collection[band_name].scale_data(inplace=inplace, **kwargs)
            else:
                # TODO: there seems to be a bug here
                band = self.get_band(band_name)
                collection.add_band(
                    band_constructor=band.scale_data,
                    inplace=True,  # within the band instance `inplace` must be True,
                    **kwargs,
                )
        return collection

    # TODO: implement this!!!
    def join(self, other):
        """
        Spatial join of one ``RasterCollection`` instance with another
        instance
        """
        pass

    def calc_si(
        self, si_name: str, inplace: Optional[bool] = False
    ) -> Union[None, np.ndarray, np.ma.MaskedArray]:
        """
        Calculates a spectral index based on color-names (set as band aliases)

        :param si_name:
            name of the spectral index to calculate (e.g., 'NDVI')
        :returns:
            ``np.ndarray`` or ``np.ma.MaskedArray`` if inplace is False, None
            otherwise (is added as band to the collection)
        """
        si_values = SpectralIndices.calc_si(si_name, self)
        # since SIs are floats by nature set the nodata value to np.nan
        nodata = np.nan
        if inplace:
            # look for spectral band with same shape to take geo-info from
            geo_info = [
                self[x].geo_info
                for x in self.band_names
                if self[x].values.shape == si_values.shape
            ][0]
            self.add_band(
                band_constructor=Band,
                band_name=si_name.upper(),
                geo_info=geo_info,
                band_alias=si_name.lower(),
                values=si_values,
                nodata=nodata,
            )
        else:
            return si_values

    @check_band_names
    def to_dataframe(
        self, band_selection: Optional[List[str]] = None
    ) -> gpd.GeoDataFrame:
        """
        Converts the bands in collection to a ``GeoDataFrame``

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :returns:
            ``GeoDataFrame`` with point-like features denoting single
            pixel values across bands in the collection
        """
        if band_selection is None:
            band_selection = self.band_names

        # get the pixel values in the selection as DataFrames and merge
        # them on the geometry column
        px_list = [self[b].to_dataframe() for b in band_selection]
        gdf = reduce(
            lambda left, right: pd.merge(left, right, on=["geometry"]), px_list
        )

        return gdf

    def to_rasterio(
        self,
        fpath_raster: Path,
        band_selection: Optional[List[str]] = None,
        use_band_aliases: Optional[bool] = False,
    ) -> None:
        """
        Writes bands in collection to a raster dataset on disk using
        ``rasterio`` drivers

        :param fpath_raster:
            file-path to the raster dataset (existing ones will be
            overwritten!)
        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :param use_band_aliases:
            use band aliases instead of band names for setting raster
            band descriptions to the output dataset
        """
        # check output file naming and driver
        try:
            driver = driver_from_extension(fpath_raster)
        except Exception as e:
            raise ValueError(
                f"Could not determine GDAL driver for " f"{fpath_raster.name}: {e}"
            )

        # check band_selection, if not provided use all available bands
        if band_selection is None:
            band_selection = self.band_names
        if len(band_selection) == 0:
            raise ValueError("No band selected for writing to raster file")

        # make sure all bands share the same extent, pixel size and CRS
        if not self.is_bandstack(band_selection):
            raise ValueError(
                "Cannot write bands with different shapes, pixels sizes "
                "and CRS to raster data set"
            )

        # check for band aliases if they shall be used
        if use_band_aliases:
            if not self.has_band_aliases:
                raise ValueError("No band aliases available")
            band_idxs = [self.band_names.index(x) for x in band_selection]
            band_selection = [self.band_aliases[x] for x in band_idxs]

        # check meta and update it with the selected driver for writing the result
        meta = deepcopy(self[band_selection[0]].meta)
        dtypes = [self[x].values.dtype for x in band_selection]
        if len(set(dtypes)) != 1:
            UserWarning(
                f"Multiple data types found in arrays to write ({set(dtypes)}). "
                f"Casting to highest data type"
            )

        if len(set(dtypes)) == 1:
            dtype_str = str(dtypes[0])
        else:
            # TODO: determine highest dtype
            dtype_str = "float32"

        # update driver, the number of bands and the metadata value
        meta.update(
            {
                "driver": driver,
                "count": len(band_selection),
                "dtype": dtype_str,
                "nodata": self[band_selection[0]].nodata,
            }
        )

        # open the result dataset and try to write the bands
        with rio.open(fpath_raster, "w+", **meta) as dst:
            for idx, band_name in enumerate(band_selection):
                # check with band name to set
                dst.set_band_description(idx + 1, band_name)
                # write band data
                band_data = self.get_band(band_name).values.astype(dtype_str)
                # set masked pixels to nodata
                if self[band_name].is_masked_array:
                    vals = band_data.data
                    mask = band_data.mask
                    vals[mask] = self[band_name].nodata
                dst.write(band_data, idx + 1)

    @check_band_names
    def to_xarray(self, band_selection: Optional[List[str]] = None) -> xr.DataArray:
        """
        Converts bands in collection a ``xarray.DataArray``

        :param band_selection:
            selection of bands to process. If not provided uses all
            bands
        :returns:
            `xarray.DataArray` created from RasterCollection.
        """
        if band_selection is None:
            band_selection = self.band_names

        # bands must have same extent, pixel size and CRS
        if not self.is_bandstack(band_selection):
            raise ValueError(
                "Selected bands must share same spatial extent, pixel size "
                "and coordinate system"
            )
        # loop over bands and convert them to xarray
        band_xarr_list = []
        band_attrs_list = []
        for band_name in band_selection:
            band_xarr = self[band_name].to_xarray()
            band_xarr_list.append(band_xarr)
            # extract attributes to avoid loosing them on concat
            band_attrs_list.append(band_xarr.attrs)

        # merge the single xarrays in the list into a single big one
        xarr = xr.concat(band_xarr_list, dim="band", combine_attrs="drop")
        # add the attributes from the concated objects
        xarr_attrs = deepcopy(band_attrs_list[0])
        for idx, band_attr in enumerate(band_attrs_list):
            # skip first band as it already serves as reference
            if idx == 0:
                continue
            for attr in xarr_attrs:
                # tuples are extended with entries from the single bands
                # except the 'transform' entry that remains the same
                # for all bands
                if isinstance(xarr_attrs[attr], tuple):
                    if attr != "transform":
                        attrs_list = list(xarr_attrs[attr])
                        attrs_list.append(band_attr[attr][0])
                        xarr_attrs.update({attr: tuple(attrs_list)})
        return xarr.assign_attrs(xarr_attrs)
