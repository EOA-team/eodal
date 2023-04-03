"""
A band is a two-dimensional array that can be located via a spatial coordinate system.
Each band thus has a name and an array of values, which are usually numeric.

It relies on ``rasterio`` for all in- and output operations to read data from files (or URIs)
using ``GDAL`` drivers.

eodal stores band data basically as ``numpy`` arrays. Masked arrays of the class
`~numpy.ma.MaskedArray` are also supported. For very large data sets that exceed the RAM of the
computer, ``zarr`` can be used.

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

import cv2
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import rasterio as rio
import rasterio.mask
import uuid
import xarray as xr
import zarr

from copy import deepcopy
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.figure import figaspect
from mpl_toolkits.axes_grid1 import make_axes_locatable
from numbers import Number
from pathlib import Path
from rasterio import Affine, features
from rasterio.coords import BoundingBox
from rasterio.crs import CRS
from rasterio.drivers import driver_from_extension
from rasterio.enums import Resampling
from rasterstats import zonal_stats
from rasterstats.utils import check_stats
from shapely.geometry import box, MultiPolygon, Point, Polygon
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from eodal.config import get_settings
from eodal.core.operators import Operator
from eodal.core.utils.geometry import check_geometry_types, convert_3D_2D
from eodal.core.utils.raster import get_raster_attributes, bounds_window
from eodal.utils.arrays import count_valid, upsample_array, array_from_points
from eodal.utils.exceptions import (
    BandNotFoundError,
    DataExtractionError,
    ResamplingFailedError,
    ReprojectionError,
)
from eodal.utils.reprojection import reproject_raster_dataset, check_aoi_geoms

Settings = get_settings()


class BandOperator(Operator):
    """
    Band operator supporting basic algebraic operations on `Band` objects
    """

    @classmethod
    def calc(
        cls,
        a,
        other: Union[Number, np.ndarray],
        operator: str,
        inplace: Optional[bool] = False,
        band_name: Optional[str] = None,
        right_sided: Optional[bool] = False,
    ) -> Union[None, np.ndarray]:
        """
        executes a custom algebraic operator on Band objects

        :param a:
            `Band` object with values (non-empty)
        :param other:
            scalar, `Band` or two-dimemsional `numpy.array` to use on the right-hand
            side of the operator. If a `numpy.array` is passed the array must
            have the same x and y dimensions as the current `Band` data.
        :param operator:
            symbolic representation of the operator (e.g., '+'
            for addition)
        :param inplace:
            returns a new `Band` object if False (default) otherwise overwrites
            the current `Band` data
        :param band_name:
            optional name of the resulting `Band` object if inplace is False.
        :param right_sided:
            optional flag indicated that the order of `a` and `other` has to be
            switched. `False` by default. Set to `True` if the order of argument
            matters, i.e., for right-hand sided expression in case of subtraction,
            division and power.
        :returns:
            `numpy.ndarray` if inplace is False, None instead
        """
        other_copy = None
        other_is_band = False
        cls.check_operator(operator=operator)
        if isinstance(other, np.ndarray) or isinstance(other, np.ma.MaskedArray):
            if other.shape != a.values.shape:
                raise ValueError(
                    f"Passed array has wrong dimensions. Expected {a.values.shape}"
                    + f" - Got {other.shape}"
                )
        elif isinstance(other, Band):
            other_copy = other.copy()
            other = other.values
            other_is_band = True
        # perform the operation
        try:
            # mind the order which is important for some operators
            if right_sided:
                expr = f"other {operator} a.values"
            else:
                expr = f"a.values {operator} other"
            res = eval(expr)
        except Exception as e:
            raise cls.BandMathError(f"Could not execute {expr}: {e}")
        # return result or overwrite band data
        if inplace:
            return a.__setattr__("values", res)
        else:
            attrs = deepcopy(a.__dict__)
            if band_name is None:
                band_name = a.band_name
                if other_is_band:
                    band_name += f"{operator}{other_copy.band_name}"
            attrs.update({"band_name": band_name})
            attrs.update({"values": res})
            return Band(**attrs)


class GeoInfo(object):
    """
    Class for storing geo-localization information required to
    reference a raster band object in a spatial coordinate system.
    At its core this class contains all the attributes necessary to
    define a ``Affine`` transformation.

    :attrib epsg:
        EPSG code of the spatial reference system the raster data is projected
        to.
    :attrib ulx:
        upper left x coordinate of the raster band in the spatial reference system
        defined by the EPSG code. We assume ``GDAL`` defaults, therefore the coordinate
        should refer to the upper left *pixel* corner.
    :attrib uly:
        upper left y coordinate of the raster band in the spatial reference system
        defined by the EPSG code. We assume ``GDAL`` defaults, therefore the coordinate
        should refer to the upper left *pixel* corner.
    :attrib pixres_x:
        pixel size (aka spatial resolution) in x direction. The unit is defined by
        the spatial coordinate system given by the EPSG code.
    :attrib pixres_y:
        pixel size (aka spatial resolution) in y direction. The unit is defined by
        the spatial coordinate system given by the EPSG code.
    """

    def __init__(
        self,
        epsg: int,
        ulx: Union[int, float],
        uly: Union[int, float],
        pixres_x: Union[int, float],
        pixres_y: Union[int, float],
    ):
        """
        Class constructor to get a new ``GeoInfo`` instance.

        >>> geo_info = GeoInfo(4326, 11., 48., 0.02, 0.02)
        >>> affine = geo_info.as_affine()

        :param epsg:
            EPSG code identifying the spatial reference system (e.g., 4326 for
            WGS84).
        :param ulx:
            upper left x coordinate in units of the spatial reference system.
            Should refer to the upper left pixel corner.
        :param uly:
            upper left x coordinate in units of the spatial reference system.
            Should refer to the upper left pixel corner
        :param pixres_x:
            pixel grid cell size in x direction in units of the spatial reference
            system.
        :param pixres_y:
            pixel grid cell size in y direction in units of the spatial reference
            system.
        """
        # make sure the EPSG code is valid
        try:
            CRS.from_epsg(epsg)
        except Exception as e:
            raise ValueError(e)

        object.__setattr__(self, "epsg", epsg)
        object.__setattr__(self, "ulx", ulx)
        object.__setattr__(self, "uly", uly)
        object.__setattr__(self, "pixres_x", pixres_x)
        object.__setattr__(self, "pixres_y", pixres_y)

    def __setattr__(self, *args, **kwargs):
        raise TypeError("GeoInfo object attributes are immutable")

    def __delattr__(self, *args, **kwargs):
        raise TypeError("GeoInfo object attributes are immutable")

    def __repr__(self) -> str:
        return str(self.__dict__)

    def as_affine(self) -> Affine:
        """
        Returns an ``rasterio.Affine`` compatible affine transformation

        :returns:
            ``GeoInfo`` instance as ``rasterio.Affine``
        """
        return Affine(
            a=self.pixres_x, b=0, c=self.ulx, d=0, e=self.pixres_y, f=self.uly
        )

    @classmethod
    def from_affine(cls, affine: Affine, epsg: int):
        """
        Returns a ``GeoInfo`` instance from a ``rasterio.Affine`` object

        :param affine:
            ``rasterio.Affine`` object
        :param epsg:
            EPSG code identifying the spatial coordinate system
        :returns:
            new ``GeoInfo`` instance
        """
        return cls(
            epsg=epsg, ulx=affine.c, uly=affine.f, pixres_x=affine.a, pixres_y=affine.e
        )


class WavelengthInfo(object):
    """
    Class for storing information about the spectral wavelength of a
    raster band. Many optical sensors record data in spectral channels
    with a central wavelength and spectral band width.

    :attrib central_wavelength:
        central spectral wavelength.
    :attrib band_width:
        spectral band width. This is defined as the difference between
        the upper and lower spectral wavelength a sensor is recording
        in a spectral channel.
    :attrib wavelength_unit:
        physical unit in which `central_wavelength` and `band_width`
        are recorded. Usually 'nm' (nano-meters) or 'um' (micro-meters)
    """

    def __init__(
        self,
        central_wavelength: Union[int, float],
        wavelength_unit: str,
        band_width: Optional[Union[int, float]] = 0.0,
    ):
        """
        Constructor to derive a new `WavelengthInfo` instance for
        a (spectral) raster band.

        :param central_wavelength:
            central wavelength of the band
        :param wavelength_unit:
            physical unit in which the wavelength is provided
        :param band_width:
            width of the spectral band (optional). If not provided
            assumes a width of zero wavelength units.
        """

        # wavelengths must be > 0:
        if central_wavelength <= 0.0:
            raise ValueError("Wavelengths must be positive!")
        # band widths must be positive numbers
        if band_width < 0:
            raise ValueError("Bandwidth must not be negative")

        object.__setattr__(self, "central_wavelength", central_wavelength)
        object.__setattr__(self, "wavelength_unit", wavelength_unit)
        object.__setattr__(self, "band_width", band_width)

    def __repr__(self) -> str:
        return str(self.__dict__)

    def __setattr__(self, *args, **kwargs):
        raise TypeError("WavelengthInfo object attributes are immutable")

    def __delattr__(self, *args, **kwargs):
        raise TypeError("WavelengthInfo object attributes are immutable")


class Band(object):
    """
    Class for storing, accessing and modifying a raster band

    :attrib band_name:
        the band name identifies the raster band (e.g., 'B1'). It can be
        any character string
    :attrib values:
        the actual raster data as ``numpy.ndarray``, ``numpy.ma.MaskedArray`` or
        ``zarr``. The type depends on how the constructor is called.
    :attrib geo_info:
        `GeoInfo` object defining the spatial reference system, upper left
        corner and pixel size (spatial resolution)
    :attrib band_alias:
        optional band alias to use in addition to `band_name`. Both, `band_name`
        and `band_alias` are interchangeable.
    :attrib wavelength_info:
        optional wavelength info about the band to allow for localizing the
        band data in the spectral domain (mostly required for data from optical
        imaging sensors).
    :attrib scale:
        scale (aka gain) parameter of the raster data.
    :attrib offset:
        offset parameter of the raster data.
    :attrib unit:
        optional (SI) physical unit of the band data (e.g., 'meters' for
        elevation data)
    :attrib nodata:
        numeric value indicating no-data. If not provided the nodata value
        is set to ``numpy.nan`` for floating point data, 0 and -999 for
        unsigned and signed integer data, respectively.
    :attrib is_tiled:
        boolean flag indicating if the raster data is sub-divided into
        tiles. False (zero) by default.
    :attrib area_or_point:
        Following ``GDAL`` standards, might be either `Area` (GDAL default) or
        `Point`. When `Area` pixel coordinates refer to the upper left corner of the
        pixel, whereas `Point` indicates that pixel coordinates are from the center
        of the pixel.
    :attrib alias:
        True if the band has a `band_alias`
    :attrib bounds:
        image bounds in cartographic projection
    :attrib coordinates:
        image coordinates in x and y direction
    :attrib crs:
        coordinate reference system as EPSG code
    :attrib has_alias:
        True if the band has a `band_alias`
    :attrib is_zarr:
        True if the band data is stored as `zarr`
    :attrib is_ndarray:
        True if the band data is stored as `numpy.ndarray`
    :attrib is_masked_array:
        True if the band data is stored as `numpy.ma.core.maskedArray`
    :attrib meta:
        `rasterio` compatible representation of essential image metadata
    :attrib transform:
        `Affine` transform representation of the image geo-localisation
    :attrib vector_features:
        `geopandas.GeoDataFrame` with vector features used for reading the image
        (clipping or masking). Can be None if no features were used for reading.
    """

    def __init__(
        self,
        band_name: str,
        values: Union[np.ndarray, np.ma.MaskedArray, zarr.core.Array],
        geo_info: GeoInfo,
        band_alias: Optional[str] = "",
        wavelength_info: Optional[WavelengthInfo] = None,
        scale: Optional[Union[int, float]] = 1.0,
        offset: Optional[Union[int, float]] = 0.0,
        unit: Optional[str] = "",
        nodata: Optional[Union[int, float]] = None,
        is_tiled: Optional[Union[int, bool]] = 0,
        area_or_point: Optional[str] = "Area",
        vector_features: Optional[gpd.GeoDataFrame] = None,
    ):
        """
        Constructor to instantiate a new band object.

        :param band_name:
            name of the band.
        :param values:
            data of the band. Can be any numpy ``ndarray`` or ``maskedArray``
            as well as a ``zarr`` instance as long as its two-dimensional.
        :param geo_info:
            `~eodal.core.band.GeoInfo` instance to allow for localizing
            the band data in a spatial reference system
        :param band_alias:
            optional alias name of the band
        :param wavelength_info:
            optional `~eodal.core.band.WavelengthInfo` instance denoting
            the spectral wavelength properties of the band. It is recommended
            to pass this parameter for optical sensor data.
        :param scale:
            optional scale (aka gain) factor for the raster band data. Many
            floating point datasets are scaled by a large number to allow for
            storing data as integer arrays to save disk space. The scale factor
            should allow to scale the data back into its original value range.
            For instance, Sentinel-2 MSI data is stored as unsigned 16-bit
            integer arrays but actually contain reflectance factor values between
            0 and 1. If not provided, `scale` is set to 1.
        :param offset:
            optional offset for the raster band data. As for the gain factor the
            idea is to scale the original band data in such a way that it's either
            possible to store the data in a certain data type or to avoid certain
            values. If not provided, `offset` is set to 0.
        :param unit:
            optional (SI) physical unit of the band data (e.g., 'meters' for
            elevation data)
        :param nodata:
            numeric value indicating no-data. If not provided the nodata value
            is set to ``numpy.nan`` for floating point data, 0 and -999 for
            unsigned and signed integer data, respectively.
        :param is_tiled:
            boolean flag indicating if the raster data is sub-divided into
            tiles. False (zero) by default.
        :param area_or_point:
            Following ``GDAL`` standards, might be either `Area` (GDAL default) or
            `Point`. When `Area` pixel coordinates refer to the upper left corner of the
            pixel, whereas `Point` indicates that pixel coordinates are from the center
            of the pixel.
        :param vector_features:
            `geopandas.GeoDataFrame` with vector features used for reading the image
            (clipping or masking). Can be None if no features were used for reading
            (optional).
        """

        # make sure the passed values are 2-dimensional
        if len(values.shape) != 2:
            raise ValueError("Only two-dimensional arrays are allowed")

        # check nodata value
        if nodata is None:
            if values.dtype in ["float16", "float32", "float64"]:
                nodata = np.nan
            elif values.dtype in ["int16", "int32", "int64"]:
                nodata = -999
            elif values.dtype in ["uint8", "uint16", "uint32", "uint64"]:
                nodata = 0

        # make sure vector features is a valid GeoDataFrame
        self._check_vector_features(vector_features)

        object.__setattr__(self, "band_name", band_name)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "geo_info", geo_info)
        object.__setattr__(self, "band_alias", band_alias)
        object.__setattr__(self, "wavelength_info", wavelength_info)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "nodata", nodata)
        object.__setattr__(self, "is_tiled", is_tiled)
        object.__setattr__(self, "area_or_point", area_or_point)
        object.__setattr__(self, "vector_features", vector_features)

    def __setattr__(self, *args, **kwargs):
        raise TypeError("Band object attributes are immutable")

    def __delattr__(self, *args, **kwargs):
        raise TypeError("Band object attributes immutable")

    def __add__(self, other):
        return BandOperator.calc(a=self, other=other, operator="+")

    def __radd__(self, other):
        return BandOperator.calc(a=self, other=other, operator="+")

    def __sub__(self, other):
        return BandOperator.calc(a=self, other=other, operator="-")

    def __rsub__(self, other):
        return BandOperator.calc(a=self, other=other, operator="-", right_sided=True)

    def __pow__(self, other):
        return BandOperator.calc(a=self, other=other, operator="**")

    def __rpow__(self, other):
        return BandOperator.calc(a=self, other=other, operator="**", right_sided=True)

    def __le__(self, other):
        return BandOperator.calc(a=self, other=other, operator="<=")

    def __rle__(self, other):
        return BandOperator.calc(a=self, other=other, operator="<=", right_sided=True)

    def __ge__(self, other):
        return BandOperator.calc(a=self, other=other, operator=">=")

    def __rge__(self, other):
        return BandOperator.calc(a=self, other=other, operator=">=", right_sided=True)

    def __truediv__(self, other):
        return BandOperator.calc(a=self, other=other, operator="/")

    def __rtruediv__(self, other):
        return BandOperator.calc(a=self, other=other, operator="/", right_sided=True)

    def __mul__(self, other):
        return BandOperator.calc(a=self, other=other, operator="*")

    def __rmul__(self, other):
        return BandOperator.calc(a=self, other=other, operator="*")

    def __ne__(self, other):
        return BandOperator.calc(a=self, other=other, operator="!=")

    def __rne__(self, other):
        return BandOperator.calc(a=self, other=other, operator="!=")

    def __eq__(self, other):
        return BandOperator.calc(a=self, other=other, operator="==")

    def __req__(self, other):
        return BandOperator.calc(a=self, other=other, operator="==")

    def __gt__(self, other):
        return BandOperator.calc(a=self, other=other, operator=">")

    def __rgt__(self, other):
        return BandOperator.calc(a=self, other=other, operator=">", right_sided=True)

    def __lt__(self, other):
        return BandOperator.calc(a=self, other=other, operator="<")

    def __rlt__(self, other):
        return BandOperator.calc(a=self, other=other, operator="<", right_sided=True)

    def __repr__(self) -> str:
        return f"EOdal Band\n---------.\nName:    {self.band_name}\nGeoInfo:    {self.geo_info}"

    @property
    def alias(self) -> Union[str, None]:
        """Alias of the band name (if available)"""
        if self.has_alias:
            return self.band_alias

    @property
    def bounds(self) -> box:
        """Spatial bounding box of the band"""
        minx = self.geo_info.ulx
        maxx = minx + self.ncols * self.geo_info.pixres_x
        maxy = self.geo_info.uly
        miny = maxy + self.nrows * self.geo_info.pixres_y
        return box(minx, miny, maxx, maxy)

    @property
    def coordinates(self) -> Dict[str, np.ndarray]:
        """x-y spatial band coordinates"""
        nx, ny = self.ncols, self.nrows
        transform = self.transform
        x, _ = transform * (np.arange(nx), np.zeros(nx))
        _, y = transform * (np.zeros(ny), np.arange(ny))

        return {"x": x, "y": y}

    @property
    def crs(self) -> CRS:
        """Coordinate Reference System of the band"""
        return CRS.from_epsg(self.geo_info.epsg)

    @property
    def has_alias(self) -> bool:
        """Checks if a color name can be used for aliasing"""
        return self.band_alias != ""

    @property
    def is_zarr(self) -> bool:
        """Checks if the band values are a zarr array"""
        return isinstance(self.values, zarr.core.Array)

    @property
    def is_ndarray(self) -> bool:
        """Checks if the band values are a numpy ndarray"""
        return isinstance(self.values, np.ndarray) and not self.is_masked_array

    @property
    def is_masked_array(self) -> bool:
        """Checks if the band values are a numpy masked array"""
        return isinstance(self.values, np.ma.MaskedArray)

    @property
    def meta(self) -> Dict[str, Any]:
        """
        Provides a ``rasterio`` compatible dictionary with raster
        metadata
        """
        return {
            "width": self.ncols,
            "height": self.nrows,
            "transform": self.geo_info.as_affine(),
            "count": 1,
            "dtype": str(self.values.dtype),
            "crs": self.crs,
        }

    @property
    def nrows(self) -> int:
        """Number of rows of the band"""
        return self.values.shape[0]

    @property
    def ncols(self) -> int:
        """Number of columns of the band"""
        return self.values.shape[1]

    @property
    def transform(self) -> Affine:
        """Affine transformation of the band"""
        return self.geo_info.as_affine()

    @staticmethod
    def _check_vector_features(vector_features: None | gpd.GeoDataFrame) -> None:
        """
        Asserts that passed GeoDataFrame has a CRS
        """
        if vector_features is not None:
            if isinstance(vector_features, Path):
                vector_features = gpd.read_file(vector_features)
            if vector_features.crs is None:
                raise ValueError(
                    f"Cannot handle vector features without spatial coordinate reference system"
                )

    @staticmethod
    def _get_pixel_geometries(
        vector_features: Union[Path, gpd.GeoDataFrame],
        fpath_raster: Optional[Path] = None,
        raster_crs: Union[int, CRS] = None,
    ) -> gpd.GeoDataFrame:
        """
        Process passed pixel geometries including reprojection of the
        vector features (if required) into the spatial reference system
        of the raster band and extraction of centroid coordinates if
        the vector features are of type ``Polygon`` or ``MultiPolygon``

        :param vector_features:
            passed vector features to calling instance or class method
        :param fpath_raster:
            optional file path to the raster dataset. To be used when
            called from a classmethod
        :param raster_crs:
            optional raster EPSG code. To be used when called from an
            instance method.
        :returns:
            ``GeoDataFrame`` with ``Point`` features for extracting
            pixel values
        """
        # check input point features
        gdf = check_aoi_geoms(
            in_dataset=vector_features,
            fname_raster=fpath_raster,
            raster_crs=raster_crs,
            full_bounding_box_only=False,
        )
        allowed_geometry_types = ["Point", "Polygon", "MultiPolygon"]
        gdf = check_geometry_types(
            in_dataset=gdf, allowed_geometry_types=allowed_geometry_types
        )

        # convert to centroids if the geometries are not of type Point
        gdf.geometry = gdf.geometry.apply(
            lambda x: x.centroid if x.type in ["Polygon", "MultiPolygon"] else x
        )

        return gdf

    @classmethod
    def from_rasterio(
        cls,
        fpath_raster: Path | Dict,
        band_idx: Optional[int] = 1,
        band_name_src: Optional[str] = "",
        band_name_dst: Optional[str] = "B1",
        vector_features: Optional[Union[Path, gpd.GeoDataFrame]] = None,
        full_bounding_box_only: Optional[bool] = False,
        epsg_code: Optional[int] = None,
        **kwargs,
    ):
        """
        Creates a new ``Band`` instance from any raster dataset understood
        by ``rasterio``. Reads exactly **one** band from the input dataset!

        NOTE:
            To read a spatial subset of raster band data only pass
            `vector_features` which can be one to N (multi)polygon features.
            For Point features refer to the `read_pixels` method.

        :param fpath_raster:
            file-path to the raster file from which to read a band or

            .. versionadd:: 0.2.0
                can be also an `assets` dictionary returned from a STAC query

        :param band_idx:
            band index of the raster band to read (starting with 1). If not
            provided the first band will be always read. Ignored if
            `band_name_src` is provided.
        :param band_name_src:
            instead of providing a band index to read (`band_idx`) a band name
            can be passed. If provided `band_idx` is ignored.
        :param band_name_dst:
            name of the raster band in the resulting ``Band`` instance. If
            not provided the default value ('B1') is used. Whenever the band
            name is known it is recommended to use a meaningful band name!
        :param vector_features:
            ``GeoDataFrame`` or file with vector features in a format understood
            by ``fiona`` with one or more vector features of type ``Polygon``
            or ``MultiPolygon``. Unless `full_bounding_box_only` is set to True
            masks out all pixels not covered by the provided vector features.
            Otherwise the spatial bounding box encompassing all vector features
            is read as a spatial subset of the input raster band.
            If the coordinate system of the vector differs from the raster data
            source the vector features are projected into the CRS of the raster
            band before extraction.
        :param full_bounding_box_only:
            if False (default) pixels not covered by the vector features are masked
            out using ``maskedArray`` in the back. If True, does not mask pixels
            within the spatial bounding box of the `vector_features`.
        :param epsg_code:
            custom EPSG code of the raster dataset in case the raster has no
            internally-described EPSG code or no EPSG code at all.
        :param kwargs:
            further key-word arguments to pass to `~eodal.core.band.Band`.
        :returns:
            new ``Band`` instance from a ``rasterio`` dataset.
        """
        _fpath_raster = deepcopy(fpath_raster)
        # check if fpath_raster is STAC item or file system path
        if isinstance(fpath_raster, dict):
            if band_name_src is not None:
                _fpath_raster = _fpath_raster[band_name_src]["href"]
            else:
                _fpath_raster = _fpath_raster[list(_fpath_raster.keys())[band_idx]][
                    "href"
                ]

        # check vector features if provided
        masking = False
        if vector_features is not None:
            masking = True
            gdf_aoi = check_aoi_geoms(
                in_dataset=vector_features,
                fname_raster=_fpath_raster,
                full_bounding_box_only=full_bounding_box_only,
            )
            # check for third dimension (has_z) and flatten it to 2d
            gdf_aoi.geometry = convert_3D_2D(gdf_aoi.geometry)

            # check geometry types of the input features
            allowed_geometry_types = ["Polygon", "MultiPolygon"]
            gdf_aoi = check_geometry_types(
                in_dataset=gdf_aoi, allowed_geometry_types=allowed_geometry_types
            )

        # read data using rasterio
        with rio.open(_fpath_raster, "r") as src:
            # parse image attributes
            attrs = get_raster_attributes(riods=src)
            transform = src.meta["transform"]
            if epsg_code is None:
                epsg = src.meta["crs"].to_epsg()
            else:
                epsg = epsg_code
            # check for area or point pixel coordinate definition
            if "area_or_point" not in kwargs.keys():
                area_or_point = src.tags().get("AREA_OR_POINT", "Area")
            else:
                area_or_point = kwargs["area_or_point"]
                kwargs.pop("area_or_point")

            # overwrite band_idx if band_name_src is provided
            band_names = list(src.descriptions)
            if band_name_src != "":
                if band_name_src not in band_names:
                    raise BandNotFoundError(
                        f'Could not find band "{band_name_src}" ' f"in {fpath_raster}"
                    )
                band_idx = band_names.index(band_name_src)

            # check if band_idx is valid
            if band_idx > len(band_names):
                raise IndexError(
                    f"Band index {band_idx} is out of range for a "
                    f"dataset with {len(band_names)} bands"
                )

            # read selected band
            if not masking:
                # TODO: add zarr support here -> when is_tile == 1
                if attrs.get("is_tile", 0) == 1:
                    pass
                band_data = src.read(band_idx)
            else:
                band_data, transform = rio.mask.mask(
                    src,
                    gdf_aoi.geometry,
                    crop=True,
                    all_touched=True,  # IMPORTANT!
                    indexes=band_idx,
                    filled=False,
                )
                # check if the mask contains any True value
                # if not cast the array from maskedArray to ndarray
                if np.count_nonzero(band_data.mask) == 0:
                    band_data = band_data.data

        # get scale, offset and unit (if available) from kwargs or the raster
        # attributes. If scale, etc. are provided in kwargs, the raster attributes
        # are ignored. If neither kwargs nor raster attributes provide information
        # about scale etc., use the defaults
        if "scale" in kwargs.keys():
            scale = kwargs["scale"]
            kwargs.pop("scale")
        else:
            scale, scales = 1, attrs.get("scales", None)
            if scales is not None:
                scale = scales[band_idx - 1]

        if "offset" in kwargs.keys():
            offset = kwargs["offset"]
            kwargs.pop("offset")
        else:
            offset, offsets = 0, attrs.get("offsets", None)
            if offsets is not None:
                offset = offsets[band_idx - 1]

        if "unit" in kwargs.keys():
            unit = kwargs["unit"]
            kwargs.pop("unit")
        else:
            unit, units = "", attrs.get("unit", None)
            if units is not None:
                unit = units[band_idx - 1]

        if "nodata" in kwargs.keys():
            nodata = kwargs["nodata"]
            kwargs.pop("nodata")
        else:
            nodata, nodata_vals = None, attrs.get("nodatavals", None)
            if nodata_vals is not None:
                nodata = nodata_vals[band_idx - 1]

        if masking:
            # make sure to set the EPSG code
            gdf_aoi.set_crs(epsg=epsg, inplace=True)
            kwargs.update({"vector_features": gdf_aoi})

        # is_tiled can only be retrived from the raster attribs
        is_tiled = attrs.get("is_tiled", 0)

        # reconstruct geo-info
        geo_info = GeoInfo(
            epsg=epsg,
            ulx=transform.c,
            uly=transform.f,
            pixres_x=transform.a,
            pixres_y=transform.e,
        )

        # create new Band instance
        return cls(
            band_name=band_name_dst,
            values=band_data,
            geo_info=geo_info,
            scale=scale,
            offset=offset,
            unit=unit,
            nodata=nodata,
            is_tiled=is_tiled,
            area_or_point=area_or_point,
            **kwargs,
        )

    @classmethod
    def from_vector(
        cls,
        vector_features: Union[Path, gpd.GeoDataFrame],
        geo_info: GeoInfo,
        band_name_src: Optional[str] = None,
        band_name_dst: Optional[str] = "B1",
        nodata_dst: Optional[Union[int, float]] = 0,
        snap_bounds: Optional[Polygon] = None,
        dtype_src: Optional[str] = "float32",
        **kwargs,
    ):
        """
        Creates a new ``Band`` instance from a ``GeoDataFrame`` or a file with
        vector features in a format understood by ``fiona`` with geometries
        of type ``Point``, ``Polygon`` or ``MultiPolygon`` using a single user-
        defined attribute (column in the data frame). The spatial reference
        system of the resulting band will be the same as for the input vector data.

        :param vector_featueres:
            file-path to a vector file or ``GeoDataFrame`` from which to convert
            a column to raster. Please note that the column must have a numerical
            data type.
        :param GeoInfo:
            `~eodal.core.band.GeoInfo` instance to allow for localizing
            the band data in a spatial reference system
        :param band_name_src:
            name of the attribute in the vector features' attribute table to
            convert to a new ``Band`` instance. If left empty generates a binary
            raster with 1 for cells overlapping the vector geometries and zero
            elsewhere.
        :param band_name_dst:
            name of the resulting ``Band`` instance. "B1" by default.
        :param nodata_dst:
            nodata value in the resulting band data to fill raster grid cells
            having no value assigned from the input vector features. If not
            provided the nodata value is set to 0 (rasterio default)
        :param dtype_src:
            data type of the resulting raster array. Per default "float32" is used.
        :param kwargs:
            additional key-word arguments to pass to `~eodal.core.Band`
        :returns:
            new ``Band`` instance from a vector features source
        """

        # check passed vector geometries
        if isinstance(vector_features, Path):
            gdf_aoi = gpd.read_file(vector_features)
        else:
            gdf_aoi = vector_features.copy()

        allowed_geometry_types = ["Point", "Polygon", "MultiPolygon"]
        in_gdf = check_geometry_types(
            in_dataset=gdf_aoi, allowed_geometry_types=allowed_geometry_types
        )

        # check if the vector features are in the CRS specified by the geo_info passed
        if in_gdf.crs != geo_info.epsg:
            in_gdf = in_gdf.to_crs(geo_info.epsg)

        # check passed attribute selection. If the band_name_src attribute does
        # not exist fill it with 1 so that a binary raster can be created
        if band_name_src is None:
            band_name_src = str(uuid.uuid4())
            in_gdf[band_name_src] = 1
        # otherwise check if the passed attribute exists
        else:
            if not band_name_src in in_gdf.columns:
                raise AttributeError(f"{band_name_src} not found")

        # infer the datatype (i.e., try if it is possible to cast the
        # attribute to float32, otherwise do not process the feature)
        try:
            in_gdf[band_name_src].astype(dtype_src)
        except ValueError as e:
            raise TypeError(f'Attribute "{band_name_src}" seems not to be numeric')

        # clip features to the spatial extent of a bounding box if available
        # clip the input to the bounds of the snap band
        if snap_bounds is not None:
            try:
                in_gdf = in_gdf.clip(mask=snap_bounds)
            except Exception as e:
                raise DataExtractionError(
                    "Could not clip input vector features to "
                    f"snap raster bounds: {e}"
                )

        # make sure there are still features left
        if in_gdf.empty:
            raise DataExtractionError("Seems there are no features to convert")

        # infer shape and affine of the resulting raster grid if not provided
        increment = 0
        if snap_bounds is None:
            if set(in_gdf.geometry.type.unique()).issubset({"Polygon", "MultiPolygon"}):
                minx = in_gdf.geometry.bounds.minx.min()
                maxx = in_gdf.geometry.bounds.maxx.max()
                miny = in_gdf.geometry.bounds.miny.min()
                maxy = in_gdf.geometry.bounds.maxy.max()
            else:
                minx = in_gdf.geometry.x.min()
                maxx = in_gdf.geometry.x.max()
                miny = in_gdf.geometry.y.min()
                maxy = in_gdf.geometry.y.max()
            snap_bounds = box(minx, miny, maxx, maxy)
            increment = 1
        else:
            minx, miny, maxx, maxy = snap_bounds.exterior.bounds

        # calculate number of columns from bounding box of all features
        # always round to the next bigger integer value to make sure no
        # value gets lost
        rows = int(np.ceil(abs((maxy - miny) / abs(geo_info.pixres_y)))) + increment
        cols = int(np.ceil(abs((maxx - minx) / geo_info.pixres_x))) + increment
        snap_shape = (rows, cols)

        # check pixel data model
        area_or_point = kwargs.get("area_or_point", "Area")

        if area_or_point == "Point":
            minx = minx - 0.5 * geo_info.pixres_x
            maxy = maxy - 0.5 * geo_info.pixres_y

        # update and create new GeoInfo instance
        geo_info = GeoInfo(
            epsg=in_gdf.crs.to_epsg(),
            ulx=minx,
            uly=maxy,
            pixres_x=geo_info.pixres_x,
            pixres_y=geo_info.pixres_y,
        )

        # rasterize the vector features. Point features work in another way than Polygons
        if (in_gdf.geom_type.unique() == ["Point"]).all():
            try:
                rasterized = array_from_points(
                    gdf=in_gdf,
                    band_name_src=band_name_src,
                    pixres_x=geo_info.pixres_x,
                    pixres_y=geo_info.pixres_y,
                    nodata_dst=nodata_dst,
                    dtype_src=dtype_src,
                )
            except Exception as e:
                raise Exception(
                    f'Could not process POINT attribute "{band_name_src}": {e}'
                )
        else:
            try:
                shapes = (
                    (geom, value)
                    for geom, value in zip(
                        in_gdf.geometry, in_gdf[band_name_src].astype(dtype_src)
                    )
                )
                rasterized = features.rasterize(
                    shapes=shapes,
                    out_shape=snap_shape,
                    transform=geo_info.as_affine(),
                    all_touched=True,
                    fill=nodata_dst,
                    dtype=dtype_src,
                )
            except Exception as e:
                raise Exception(
                    f'Could not process MULTI/POLYGON attribute "{band_name_src}": {e}'
                )

        # initialize new Band instance
        return cls(
            band_name=band_name_dst,
            values=rasterized,
            geo_info=geo_info,
            nodata=nodata_dst,
            **kwargs,
        )

    @classmethod
    def read_pixels(
        cls,
        fpath_raster: Path,
        vector_features: Union[Path, gpd.GeoDataFrame],
        band_idx: Optional[int] = 1,
        band_name_src: Optional[str] = "",
        band_name_dst: Optional[str] = "B1",
    ) -> gpd.GeoDataFrame:
        """
        Reads single pixel values from a raster dataset into a ``GeoDataFrame``

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
        :param band_idx:
            band index of the raster band to read (starting with 1). If not
            provided the first band will be always read. Ignored if
            `band_name_src` is provided.
        :param band_name_src:
            instead of providing a band index to read (`band_idx`) a band name
            can be passed. If provided `band_idx` is ignored. NOTE: This works
            *only* if the raster dataset has band names set in its descriptions
            (often not the case)!
        :param band_name_dst:
            name of the raster band in the resulting ``GeoDataFrame`` (i.e.,
            column name)
        :returns:
            ``GeoDataFrame`` with extracted pixel values. If the vector features
            defining the sampling points are not within the spatial extent of the
            raster dataset the pixel values are set to nodata (inferred from
            the raster source)
        """
        # check input point features
        gdf = cls._get_pixel_geometries(
            vector_features=vector_features, fpath_raster=fpath_raster
        )

        # use rasterio.sample to extract the pixel values from the raster
        # to do so, we need a list of coordinate tuples
        coord_list = [(x, y) for x, y in zip(gdf.geometry.x, gdf["geometry"].y)]
        with rio.open(fpath_raster, "r") as src:
            # overwrite band_idx if band_name_src is provided and band names
            # is not None (otherwise the band index cannot be determined)
            band_names = list(src.descriptions)
            if not set(band_names) == {None}:
                if band_name_src != "":
                    if band_name_src not in band_names:
                        raise BandNotFoundError(
                            f'Could not find band "{band_name_src}" '
                            f"in {fpath_raster}"
                        )
                    band_idx = band_names.index(band_name_src) + 1
            try:
                # yield all values from the generator
                def _sample(src, coord_list, band_idx):
                    yield from src.sample(coord_list, band_idx)

                pixel_samples = list(_sample(src, coord_list, band_idx))
            except Exception as e:
                raise Exception(f"Extraction of pixels from raster failed: {e}")

        # append the extracted pixels to the exisiting geodataframe. We can do
        # so, because we have passed the pixels in the same order as they occur
        # in the dataframe
        band_list = [x[0] for x in pixel_samples]
        gdf[band_name_dst] = band_list

        return gdf

    def _flatten_coordinates(self) -> Dict[str, np.array]:
        """
        Flattens band coordinates. To be used when converting an array to
        ``geopandas.GeoDataFrame``.

        :returns:
            dictionary of ``numpy.ndarray`` containing the x and y
            coordinates in flattened format to match the flattened band
            values in ``Fortran`` order
        """

        # get coordinates
        coords = self.coordinates
        # flatten x coordinates along the y-axis
        flat_x_coords = np.repeat(coords["x"], self.nrows)
        # flatten y coordinates along the x-axis
        flat_y_coords = np.tile(coords["y"], self.ncols)

        out_coords = {"x": flat_x_coords, "y": flat_y_coords}

        return out_coords

    def copy(self):
        """
        Returns a copy of the current ``Band`` instance
        """
        attrs = deepcopy(self.__dict__)
        return Band(**attrs)

    def clip(
        self,
        clipping_bounds: Path
        | gpd.GeoDataFrame
        | gpd.GeoSeries
        | Tuple[float, float, float, float]
        | Polygon
        | MultiPolygon,
        full_bounding_box_only: Optional[bool] = False,
        inplace: Optional[bool] = False,
    ):
        """
        Clip a band object to a geometry or the bounding box of one or more
        geometries. By default, pixel values outside the geometry are masked.
        The spatial extent of the returned `Band` instance is **always** cropped
        to the bounding box of the geomtry/ geometries.

        NOTE:
            When passing a `GeoDataFrame` with more than one feature, the single
            feature geometries are dissolved into a single one!

        :param clipping_bounds:
            spatial bounds to clip the Band to. Can be either a vector file, a shapely
            `Polygon` or `MultiPolygon`, a `GeoDataFrame`, `GeoSeries` or a coordinate tuple with
            (xmin, ymin, xmax, ymax).
            Vector files and `GeoDataFrame` are reprojected into the bands' coordinate
            system if required, while the coordinate tuple and shapely geometry **MUST**
            be provided in the CRS of the band.
        :param full_bounding_box_only:
            if False (default), clips to the bounding box of the geometry and masks values
            outside the actual geometry boundaries. To obtain all values within the
            bounding box set to True.
            .. versionadded:: 0.1.1
        :param inplace:
            if False (default) returns a copy of the ``Band`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :returns:
            clipped band instance.
        """
        # prepare geometries
        if isinstance(clipping_bounds, Path):
            clipping_bounds = gpd.read_file(clipping_bounds)
        if isinstance(clipping_bounds, gpd.GeoSeries):
            clipping_bounds = gpd.GeoDataFrame(geometry=clipping_bounds)
        if isinstance(clipping_bounds, tuple):
            if len(clipping_bounds) != 4:
                raise ValueError("Expected four coordinates (xmin, ymin, xmax, ymax)")
            xmin, ymin, xmax, ymax = clipping_bounds
            clipping_bounds = box(*clipping_bounds)

        # get bounding box
        if isinstance(clipping_bounds, gpd.GeoDataFrame):
            # reproject GeoDataFrame if necessary
            _clipping_bounds = clipping_bounds.copy()
            _clipping_bounds.to_crs(epsg=self.geo_info.epsg, inplace=True)
            # get the bounding box of the FIRST feature
            _clipping_bounds_boundaries = _clipping_bounds.bounds
            xmin, ymin, xmax, ymax = _clipping_bounds_boundaries.values[0]
            # the actual geometries are dissolved in case there is more than one record
            # and converted to a shapely object
            actual_geom = _clipping_bounds.dissolve().geometry.values[0]
        elif isinstance(clipping_bounds, Polygon) or isinstance(
            clipping_bounds, MultiPolygon
        ):
            xmin, ymin, xmax, ymax = clipping_bounds.bounds
            actual_geom = clipping_bounds
        else:
            raise TypeError(f"{type(clipping_bounds)} is not supported")

        # make sure xmax and xmin as well as ymax and ymin are not the same
        if xmax == xmin:
            raise ValueError("Cannot handle extent of zero length in x direction")
        if ymax == ymin:
            raise ValueError("Cannot handle extent of zero length in y direction")

        # actual clipping operation. Calculate the rows and columns where to clip
        # the band
        clip_shape = box(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax)
        # check for overlap first
        if not (
            clip_shape.overlaps(self.bounds)
            or self.bounds.covers(clip_shape)
            or self.bounds.equals(clip_shape)
            or self.bounds.overlaps(clip_shape)
            or clip_shape.covers(self.bounds)
        ):
            raise ValueError(f"Clipping bounds do not overlap Band")
        # then determine the extent in image coordinates by search for the closest image
        # pixels
        row_start, row_stop, col_start, col_stop = bounds_window(
            bounds=(xmin, ymin, xmax, ymax), affine=self.geo_info.as_affine()
        )

        # adopt bounds if clip shape is larger than the Band's spatial extent
        if row_start < 0:
            row_start = 0
        if row_stop > self.nrows:
            row_stop = self.nrows
        if col_start < 0:
            col_start = 0
        if col_start > self.ncols:
            col_stop = self.ncols

        # get upper left coordinate tuple
        ulx, _ = self.geo_info.as_affine() * (col_start, row_stop)
        _, uly = self.geo_info.as_affine() * (col_stop, row_start)

        # get its GeoInfo and update it accordingly
        geo_info = self.geo_info
        new_geo_info = GeoInfo(
            epsg=geo_info.epsg,
            ulx=ulx,
            uly=uly,
            pixres_x=geo_info.pixres_x,
            pixres_y=geo_info.pixres_y,
        )
        values = self.values.copy()
        new_values = values[row_start:row_stop, col_start:col_stop]

        # if full_bounding_box is False, mask out pixels not overlapping the
        # geometry (but located within the bounding box)
        if not full_bounding_box_only:
            # to mask pixels outside the geometry we need to rasterize it
            # Rasterize vector using the shape and coordinate system of the raster
            mask = features.rasterize(
                [actual_geom],
                out_shape=new_values.shape,
                fill=1,
                out=None,
                transform=new_geo_info.as_affine(),
                all_touched=True,
                default_value=0,
                dtype="uint8",
            ).astype(bool)
            new_values = np.ma.MaskedArray(data=new_values, mask=mask)

        if inplace:
            object.__setattr__(self, "values", new_values)
            object.__setattr__(self, "geo_info", new_geo_info)
        else:
            attrs = deepcopy(self.__dict__)
            attrs.update({"values": new_values, "geo_info": new_geo_info})
            return Band(**attrs)

    def get_attributes(self, **kwargs) -> Dict[str, Any]:
        """
        Returns raster data attributes in ``rasterio`` compatible way

        :param kwargs:
            key-word arguments to insert into the raster attributes
        :returns:
            dictionary compatible with ``rasterio`` attributes
        """
        attrs = {}
        attrs["is_tiled"] = self.is_tiled
        attrs["nodatavals"] = (self.nodata,)
        attrs["scales"] = (self.scale,)
        attrs["offsets"] = (self.offset,)
        attrs["descriptions"] = (self.band_alias,)
        attrs["crs"] = self.geo_info.epsg
        attrs["transform"] = tuple(self.transform)
        attrs["units"] = (self.unit,)
        attrs.update(kwargs)

        return attrs

    def get_meta(self, driver: Optional[str] = "gTiff", **kwargs) -> Dict[str, Any]:
        """
        Returns a ``rasterio`` compatible dictionary with raster dataset
        metadata.

        :param driver:
            name of the ``rasterio`` driver. `gTiff` (GeoTiff) by default
        :param kwargs:
            additional keyword arguments to append to metadata dictionary
        :returns:
            ``rasterio`` compatible metadata dictionary to be used for
            writing new raster datasets
        """
        meta = {}
        meta["height"] = self.nrows
        meta["width"] = self.ncols
        meta["crs"] = self.crs
        meta["dtype"] = str(self.values.dtype)
        meta["count"] = 1
        meta["nodata"] = self.nodata
        meta["transform"] = self.transform
        meta["is_tile"] = self.is_tiled
        meta["driver"] = driver
        meta.update(kwargs)

        return meta

    def get_pixels(self, vector_features: Union[Path, gpd.GeoDataFrame]):
        """
        Returns pixel values from a ``Band`` instance raster values.

        The extracted band array values are stored in a new column in the
        returned `vector_features` ``GeoDataFrame`` named like the name
        of the band.

        If you do not want to read the entire raster data first consider
        using `~eodal.core.Band.read_pixels` instead.

        NOTE:
            Masked pixels are set to the band's nodata value.

        :param vector_features:
            file-path or ``GeoDataFrame`` to features defining the pixels to read
            from the ``Band`` raster values. The geometries can be of type ``Point``,
            ``Polygon`` or ``MultiPolygon``. In the latter two cases the centroids
            are used to extract pixel values, whereas for point features the
            closest raster grid cell is selected.
        """

        # get pixel point features
        gdf = self._get_pixel_geometries(
            vector_features=vector_features, raster_crs=self.crs
        )

        # drop points outside of the band's bounding box (speeds up the process)
        band_bbox = BoundingBox(*self.bounds.exterior.bounds)
        gdf = gdf.cx[band_bbox.left : band_bbox.right, band_bbox.bottom : band_bbox.top]

        # define helper function for getting the closest array index for a coordinate
        # map the coordinates to array indices
        def _find_nearest_array_index(array, value):
            return np.abs(array - value).argmin()

        # calculate the x and y array indices required to extract the pixel values
        gdf["x"] = gdf.geometry.x
        gdf["y"] = gdf.geometry.y

        # get band coordinates
        coords = self.coordinates

        # get column (x) indices
        gdf["col"] = gdf["x"].apply(
            lambda x, coords=coords, find_nearest_array_index=_find_nearest_array_index: find_nearest_array_index(
                coords["x"], x
            )
        )
        # get row (y) indices
        gdf["row"] = gdf["y"].apply(
            lambda y, coords=coords, find_nearest_array_index=_find_nearest_array_index: find_nearest_array_index(
                coords["y"], y
            )
        )

        # add column to store band values
        gdf[self.band_name] = np.empty(gdf.shape[0])

        # loop over sample points and add them as new entries to the GeoDataFrame
        for _, record in gdf.iterrows():
            # get array value for the current column and row, continue on out-of-bounds error
            try:
                array_value = self.values[record.row, record.col]
            except IndexError:
                continue
            # ignore masked pixels
            if self.is_masked_array:
                if self.values.mask[record.row, record.col]:
                    array_value = self.nodata
            gdf.loc[
                (gdf.row == record.row) & (gdf.col == record.col), self.band_name
            ] = array_value

        # clean up GeoDataFrame
        cols_to_drop = ["row", "col", "x", "y"]
        for col_to_drop in cols_to_drop:
            gdf.drop(col_to_drop, axis=1, inplace=True)

        return gdf

    def hist(
        self,
        ax: Optional[Axes] = None,
        ylabel: Optional[str] = None,
        xlabel: Optional[str] = None,
        fontsize: Optional[int] = 12,
        **kwargs,
    ) -> plt.Figure:
        """
        Plots the raster histogram using ``matplotlib``

        :param nbins:
            optional number of histogram bins
        :param ax:
            optional `matplotlib.axes` object to plot onto
        :param ylabel:
            optional y axis label
        :param xlabel:
            optional x axis label
        :param fontsize:
            fontsize to use for axes labels, plot title and colorbar label.
            12 pts by default.
        """
        # open figure and axes for plotting
        if ax is None:
            fig, ax = plt.subplots(nrows=1, ncols=1, num=1, clear=True)
        # or get figure from existing axis object passed
        else:
            fig = ax.get_figure()
        vals = self.values.flatten()
        ax.hist(vals[~np.isnan(vals)], **kwargs)
        if xlabel is None:
            xlabel = self.band_name
        if ylabel is None:
            ylabel = "Frequency"
        ax.set_xlabel(xlabel, fontsize=fontsize)
        ax.set_ylabel(ylabel, fontsize=fontsize)

        return fig

    def plot(
        self,
        colormap: Optional[str] = "gray",
        discrete_values: Optional[bool] = False,
        user_defined_colors: Optional[ListedColormap] = None,
        user_defined_ticks: Optional[List[Union[str, int, float]]] = None,
        colorbar_label: Optional[str] = None,
        vmin: Optional[Union[int, float]] = None,
        vmax: Optional[Union[int, float]] = None,
        fontsize: Optional[int] = 12,
        ax: Optional[Axes] = None,
    ) -> plt.Figure:
        """
        Plots the raster values using ``matplotlib``

        :param colormap:
            String identifying one of matplotlib's colormaps.
            The default will plot the band in gray values.
        :param discrete_values:
            if True (Default) assumes that the band has continuous values
            (i.e., ordinary spectral data). If False assumes that the
            data only takes a limited set of discrete values (e.g., in case
            of a classification or mask layer).
        :param user_defined_colors:
            possibility to pass a custom, i.e., user-created color map object
            not part of the standard matplotlib color maps. If passed, the
            ``colormap`` argument is ignored.
        :param user_defined_ticks:
            list of ticks to overwrite matplotlib derived defaults (optional).
        :param colorbar_label:
            optional text label to set to the colorbar.
        :param vmin:
            lower value to use for `~matplotlib.pyplot.imshow()`. If None it
            is set to the lower 5% percentile of the data to plot.
        :param vmin:
            upper value to use for `~matplotlib.pyplot.imshow()`. If None it
            is set to the upper 95% percentile of the data to plot.
        :param fontsize:
            fontsize to use for axes labels, plot title and colorbar label.
            12 pts by default.
        :param ax:
            optional `matplotlib.axes` object to plot onto
        :returns:
            matplotlib figure object with the band data
            plotted as map
        """
        # get the bounds of the band
        bounds = BoundingBox(*self.bounds.exterior.bounds)

        # determine intervals for plotting and aspect ratio (figsize)
        east_west_dim = bounds.right - bounds.left
        if abs(east_west_dim) < 5000:
            x_interval = 500
        elif abs(east_west_dim) >= 5000 and abs(east_west_dim) < 100000:
            x_interval = 5000
        else:
            x_interval = 50000
        north_south_dim = bounds.top - bounds.bottom
        if abs(north_south_dim) < 5000:
            y_interval = 500
        elif abs(north_south_dim) >= 5000 and abs(north_south_dim) < 100000:
            y_interval = 5000
        else:
            y_interval = 50000

        w_h_ratio = figaspect(east_west_dim / north_south_dim)

        # open figure and axes for plotting
        if ax is None:
            fig, ax = plt.subplots(
                nrows=1, ncols=1, figsize=w_h_ratio, num=1, clear=True
            )
        # or get figure from existing axis object passed
        else:
            fig = ax.get_figure()

        # get color-map
        cmap = user_defined_colors
        if cmap is None:
            cmap = plt.cm.get_cmap(colormap)

        # check if data is continuous (spectral) or discrete (np.unit8)
        if discrete_values:
            # define the bins and normalize
            unique_values = np.unique(self.values)
            norm = mpl.colors.BoundaryNorm(unique_values, cmap.N)
            img = ax.imshow(
                self.values,
                cmap=cmap,
                norm=norm,
                extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
                interpolation="none",  # important, otherwise img will have speckle!
            )
        else:
            # clip data for displaying to central 96% percentile
            # TODO: here seems to be a bug with nans in the data ...
            if vmin is None:
                try:
                    vmin = np.nanquantile(self.values, 0.02)
                except ValueError:
                    vmin = self.values.min()
            if vmax is None:
                try:
                    vmax = np.nanquantile(self.values, 0.98)
                except ValueError:
                    vmax = self.values.max()

            # actual displaying of the band data
            img = ax.imshow(
                self.values,
                vmin=vmin,
                vmax=vmax,
                extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
                cmap=cmap,
            )

        # add colorbar (does not apply in RGB case)
        if colormap is not None:
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.05)
            if discrete_values:
                cb = fig.colorbar(
                    img,
                    cax=cax,
                    orientation="vertical",
                    ticks=unique_values,
                    extend="max",
                )
            else:
                cb = fig.colorbar(img, cax=cax, orientation="vertical")
            # overwrite ticker if user defined ticks provided
            if user_defined_ticks is not None:
                # TODO: there seems to be one tick missing (?)
                cb.ax.locator_params(nbins=len(user_defined_ticks))
                cb.set_ticklabels(user_defined_ticks)
            # add colorbar label text if provided
            if colorbar_label is not None:
                cb.set_label(
                    colorbar_label, rotation=270, fontsize=fontsize, labelpad=20, y=0.5
                )

        title_str = self.band_name
        if self.has_alias:
            title_str += f" ({self.alias})"
        ax.title.set_text(title_str)
        # add axes labels and format ticker
        epsg = self.geo_info.epsg
        if self.crs.is_geographic:
            unit = "deg"
        elif self.crs.is_projected:
            unit = "m"
        ax.set_xlabel(f"X [{unit}] (EPSG:{epsg})", fontsize=fontsize)
        ax.xaxis.set_ticks(np.arange(bounds.left, bounds.right, x_interval))
        ax.set_ylabel(f"Y [{unit}] (EPSG:{epsg})", fontsize=fontsize)
        ax.yaxis.set_ticks(np.arange(bounds.bottom, bounds.top, y_interval))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))

        return fig

    def mask(self, mask: np.ndarray, inplace: Optional[bool] = False):
        """
        Mask out pixels based on a boolean array.

        NOTE:
            If the band is already masked, the new mask updates the
            existing one. I.e., pixels already masked before remain
            masked.

        :param mask:
            ``numpy.ndarray`` of dtype ``boolean`` to use as mask.
            The mask must match the shape of the raster data.
        :param inplace:
            if False (default) returns a copy of the ``Band`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :returns:
            ``Band`` instance if `inplace` is False, None instead.
        """

        # check shape of mask passed and its dtype
        if mask.dtype != "bool":
            raise TypeError("Mask must be boolean")

        if mask.shape != self.values.shape:
            raise ValueError(
                f"Shape of mask {mask.shape} does not match "
                f"shape of band data {self.values.shape}"
            )

        # check if array is already masked
        if self.is_masked_array:
            orig_mask = self.values.mask
            # update the existing mask
            for row in range(self.nrows):
                for col in range(self.ncols):
                    # ignore pixels already masked
                    if not orig_mask[row, col]:
                        orig_mask[row, col] = mask[row, col]
            # update band data array
            masked_array = np.ma.MaskedArray(data=self.values.data, mask=orig_mask)
        elif self.is_ndarray:
            masked_array = np.ma.MaskedArray(data=self.values, mask=mask)
        elif self.is_zarr:
            raise NotImplemented()

        if inplace:
            object.__setattr__(self, "values", masked_array)
        else:
            attrs = deepcopy(self.__dict__)
            attrs.update({"values": masked_array})
            return Band(**attrs)

    def rename(
        self,
        name: str,
        alias: Optional[bool] = False,
        autoupdate_alias: Optional[bool] = True,
    ) -> None:
        """
        Sets a new band name or alias

        :param name:
            new band name or alias
        :param alias:
            if False (defaults) renames the actual band name, otherwise changes
            the alias
        :param autoupdate_alias:
            if True (default) the band alias is set to the same value as the band
            name if `alias==False`
        """
        if not isinstance(name, str) or name == "":
            raise ValueError(
                f"Invalid name {name} - only non-empty strings are allowed"
            )
        # auto-update the band alias
        if alias or autoupdate_alias:
            object.__setattr__(self, "band_alias", name)
        if not alias:
            object.__setattr__(self, "band_name", name)

    def resample(
        self,
        target_resolution: Union[int, float],
        interpolation_method: Optional[int] = cv2.INTER_NEAREST_EXACT,
        target_shape: Optional[Tuple[int, int]] = None,
        inplace: Optional[bool] = False,
    ):
        """
        Changes the raster grid cell (pixel) size.
        Nodata pixels are not used for resampling.

        :param target_resolution:
            spatial resolution (grid cell size) in units of the spatial
            reference system. Applies to x and y direction.
        :param interpolation_method:
            opencv interpolation method. Per default nearest neighbor
            interpolation is used (`~cv2.INTER_NEAREST_EXACT`). See the
            `~cv2` documentation for a list of available methods.
        :param target_shape:
            shape of the output in terms of number of rows and columns.
            If None (default) the `target_shape` parameter is inferred
            from the band data. If you want to make sure the output is
            *aligned* with another raster band (co-registered) provide
            this parameter.
        :param inplace:
            if False (default) returns a copy of the ``Band`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :returns:
            ``Band`` instance if `inplace` is False, None instead.
        """
        # resampling currently works on grids with identitical x and y
        # grid cell size only
        if abs(self.geo_info.pixres_x) != abs(self.geo_info.pixres_y):
            raise NotImplementedError(
                "Resampling currently supports regular grids only "
                "where the grid cell size is the same in x and y "
                "direction"
            )

        # if band has already the target resolution there's nothing to do
        if (
            abs(self.geo_info.pixres_x) == target_resolution
            and abs(self.geo_info.pixres_y) == target_resolution
        ):
            if inplace:
                return
            else:
                return self.copy()

        # check if a target shape is provided
        if target_shape is not None:
            nrows_resampled = target_shape[0]
            ncols_resampled = target_shape[1]
        # if not determine the extent from the bounds
        else:
            bounds = BoundingBox(*self.bounds.exterior.bounds)
            # calculate new size of the raster
            ncols_resampled = int(
                np.ceil((bounds.right - bounds.left) / target_resolution)
            )
            nrows_resampled = int(
                np.ceil((bounds.top - bounds.bottom) / target_resolution)
            )
            target_shape = (nrows_resampled, ncols_resampled)

        # opencv2 switches the axes order!
        dim_resampled = (ncols_resampled, nrows_resampled)

        # check if the band data is stored in a masked array
        # if so, replace the masked values with NaN
        if self.is_masked_array:
            band_data = deepcopy(self.values.data)
        elif self.is_ndarray:
            band_data = deepcopy(self.values)
        elif self.is_zarr:
            raise NotImplementedError()

        scaling_factor = abs(self.geo_info.pixres_x / target_resolution)
        blackfill_value = self.nodata

        # we have to take care about no-data pixels
        valid_pixels = count_valid(in_array=band_data, no_data_value=blackfill_value)
        all_pixels = band_data.shape[0] * band_data.shape[1]
        # if all pixels are valid, then we can directly proceed to the resampling
        if valid_pixels == all_pixels:
            try:
                res = cv2.resize(
                    band_data, dsize=dim_resampled, interpolation=interpolation_method
                )
            except Exception as e:
                raise ResamplingFailedError(e)
        else:
            # blackfill pixel should be set to NaN before resampling
            type_casting = False
            if band_data.dtype in [
                "uint8",
                "uint16",
                "uint32",
                "int8",
                "int16",
                "int32",
                "int64",
            ]:
                tmp = deepcopy(band_data).astype(float)
                type_casting = True
            else:
                tmp = deepcopy(band_data)
            tmp[tmp == blackfill_value] = np.nan
            # resample data
            try:
                res = cv2.resize(
                    tmp, dsize=dim_resampled, interpolation=interpolation_method
                )
            except Exception as e:
                raise ResamplingFailedError(e)

            # in addition, run pixel division since there will be too many NaN pixels
            # when using only res from cv2 resize as it sets pixels without full
            # spatial context to NaN. This works, however, only if the target resolution
            # decreases the current pixel resolution by an integer scalar
            try:
                res_pixel_div = upsample_array(
                    in_array=band_data, scaling_factor=int(scaling_factor)
                )
            except Exception as e:
                res_pixel_div = np.zeros(0)

            # replace NaNs with values from pixel division (if possible); thus we will
            # get all pixel values and the correct blackfill
            # when working on spatial subsets this might fail because of shape mismatches;
            # in this case keep the cv2 output, which means loosing a few pixels
            if res.shape == res_pixel_div.shape:
                res[np.isnan(res)] = res_pixel_div[np.isnan(res)]
            else:
                res[np.isnan(res)] = blackfill_value

            # cast back to original datatype if required
            if type_casting:
                res = res.astype(band_data.dtype)

        # if the array is masked, resample the mask as well
        if self.is_masked_array:
            # convert bools to int8 (cv2 does not support boolean arrays)
            in_mask = deepcopy(self.values.mask).astype("uint8")
            out_mask = cv2.resize(in_mask, dim_resampled, cv2.INTER_NEAREST_EXACT)
            # convert mask back to boolean array
            out_mask = out_mask.astype(bool)
            # save as masked array
            res = np.ma.masked_array(data=res, mask=out_mask)

        # update the geo_info with new pixel resolution. The upper left x and y
        # coordinate must be changed if the pixel coordinates refer to the center
        # of the pixel (AREA_OR_POINT == Point)
        geo_info = deepcopy(self.geo_info.__dict__)
        geo_info.update(
            {
                "pixres_x": np.sign(self.geo_info.pixres_x) * target_resolution,
                "pixres_y": np.sign(self.geo_info.pixres_y) * target_resolution,
            }
        )
        if self.area_or_point == "Point":
            center_shift = (target_resolution - abs(self.geo_info.pixres_x)) * 0.5
            ulx_new = self.geo_info.ulx + center_shift * np.sign(self.geo_info.pixres_x)
            uly_new = self.geo_info.uly + center_shift * np.sign(self.geo_info.pixres_y)
            geo_info.update({"ulx": ulx_new, "uly": uly_new})
        new_geo_info = GeoInfo(**geo_info)

        if inplace:
            object.__setattr__(self, "values", res)
            object.__setattr__(self, "geo_info", new_geo_info)
        else:
            attrs = deepcopy(self.__dict__)
            attrs.update({"values": res, "geo_info": new_geo_info})
            return Band(**attrs)

    def reproject(
        self,
        target_crs: Union[int, CRS],
        dst_transform: Optional[Affine] = None,
        interpolation_method: Optional[int] = Resampling.nearest,
        num_threads: Optional[int] = 1,
        inplace: Optional[bool] = False,
        **kwargs,
    ):
        """
        Projects the raster data into a different spatial coordinate system

        :param target_crs:
            EPSG code of the target spatial coordinate system the raster data
            should be projected to
        :param dst_transfrom:
            optional ``Affine`` transformation of the raster data in the target
            spatial coordinate system
        :param interpolation_method:
            interpolation method to use for interpolating grid cells after
            reprojection. Default is neares neighbor interpolation.
        :param num_threads:
            number of threads to use for the operation. Uses a single thread by
            default.
        :param inplace:
            if False (default) returns a copy of the ``Band`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :returns:
            ``Band`` instance if `inplace` is False, None instead.
        """

        # collect options for reprojection
        reprojection_options = {
            "src_crs": self.crs,
            "src_transform": self.transform,
            "dst_crs": target_crs,
            "src_nodata": self.nodata,
            "resampling": interpolation_method,
            "num_threads": num_threads,
            "dst_transform": dst_transform,
        }
        reprojection_options.update(kwargs)

        # check for array type; masked arrays are not supported directly
        # also we have to cast to float for performing the reprojection
        if self.is_masked_array:
            band_data = deepcopy(self.values.data).astype(float)
            band_mask = deepcopy(self.values.mask).astype(float)
        elif self.is_ndarray:
            band_data = deepcopy(self.values).astype(float)
        elif self.is_zarr:
            raise NotImplementedError()

        try:
            # set destination array in case dst_transfrom is provided
            if (
                "dst_transform" in reprojection_options.keys()
                and reprojection_options.get("dst_transfrom") is not None
            ):
                if "destination" not in reprojection_options.keys():
                    dst = np.zeros_like(band_data)
                    reprojection_options.update({"destination": dst})

            out_data, out_transform = reproject_raster_dataset(
                raster=band_data, **reprojection_options
            )
        except Exception as e:
            raise ReprojectionError(f"Could not re-project band {self.band_name}: {e}")

        # cast array back to original dtype
        out_data = out_data[0, :, :].astype(self.values.dtype)

        # reproject the mask separately
        if self.is_masked_array:
            out_mask, _ = reproject_raster_dataset(
                raster=band_mask, **reprojection_options
            )
            out_mask = out_mask[0, :, :].astype(bool)
            # mask also those pixels which were set to nodata after reprojection
            # due to the raster alignment
            nodata = reprojection_options.get("src_nodata", 0)
            out_mask[out_data == nodata] = True
            out_data = np.ma.MaskedArray(data=out_data, mask=out_mask)

        new_geo_info = GeoInfo.from_affine(affine=out_transform, epsg=target_crs)
        if inplace:
            object.__setattr__(self, "values", out_data)
            object.__setattr__(self, "geo_info", new_geo_info)
        else:
            attrs = deepcopy(self.__dict__)
            attrs.update({"values": out_data, "geo_info": new_geo_info})
            return Band(**attrs)

    def reduce(
        self,
        method: Optional[
            List[str | Callable[np.ndarray | np.ma.MaskedArray, Number]]
        ] = ["min", "mean", "std", "max", "count"],
        by: Optional[Path | gpd.GeoDataFrame | Polygon | str] = None,
        keep_nans: Optional[bool] = False,
    ) -> List[Dict[str, int | float]]:
        """
        Reduces the raster data to scalar values by calling `rasterstats`.

        The reduction can be done on the whole band or by using vector features.

        IMPORTANT:
            NaNs in the data are handled by `rasterstats` internally. Therefore, passing
            numpy nan-functions (e.g., `nanmedian`) is **NOT** necessary and users are
            **discouraged** from doing so as passing `nanmedian` will ignore existing
            masks.

        :param method:
            list of `numpy` function names and/ or custom function prototypes to use
            for reducing raster data. Please see also the official `rasterstats` docs
            /https://pythonhosted.org/rasterstats/manual.html#user-defined-statistics)
            about how to pass custom functions.
        :param by:
            define optional vector features by which to reduce the band. By passing
            `'self'` the method uses the features with which the band was read, otherwise
            specify a file-path to vector features or provide a GeoDataFrame.
        :param keep_nans:
            .. versionadded:: 0.2.0
            whether to keep or discard results that were `nan`. This could happen
            if a feature does not overlap the raster.
        :returns:
            list of dictionaries with scalar results per feature including
            their geometry and further attributes
        """
        # check by what features the Band should be reduced spatially
        # if `by` is None use the full spatial extent of the band
        if by is None:
            features = gpd.GeoDataFrame(geometry=[self.bounds], crs=self.crs)
        else:
            if isinstance(by, str):
                if by == "self":
                    features = deepcopy(self.vector_features)
                else:
                    raise ValueError("When passing a string you must pass `self`")
            elif isinstance(by, Path):
                features = gpd.read_file(by)
            elif isinstance(by, gpd.GeoDataFrame):
                features = deepcopy(by)
            elif isinstance(by, Polygon) or isinstance(by, MultiPolygon):
                features = gpd.GeoDataFrame(geometry=[by], crs=self.crs)
            else:
                raise TypeError(
                    'by expected "self", Path, (Multi)Polygon and GeoDataFrame '
                    + f"objects - got {type(by)} instead"
                )
        # check if features has the same CRS as the band. Reproject features if required
        if not features.crs == self.crs:
            features.to_crs(crs=self.crs, inplace=True)

        # check method string passed
        if isinstance(method, str):
            method = [method]

        # compute statistics by calling rasterstats. rasterstats needs the
        # Affine transformation matrix to work on numpy arrays
        affine = self.geo_info.as_affine()
        # check the passed functions. Depending on the type passed rasterstats
        # has to be called slightly differently
        stats = ["count"]  # set the default to count to bypass rasterstats defaults
        add_stats = {}
        stats_operator_list = []
        # loop over operators in method list and make them rasterstats compatible
        for operator in method:
            # check if operator passed is a string
            if isinstance(operator, str):
                # the usage of nan-functions is discouraged
                if operator.startswith("nan"):
                    raise ValueError(
                        "The usage of numpy-nan functions is discouraged and therefore raises an error."
                        + "\nThe handling of NaNs is done by `rasterstats` internally and therefore does not"
                        + '\n need to be specified. Please pass operators by their standard numpy names (e.g., "mean")'
                    )
                # check if the operator is a standard rasterstats operator
                # raises a ValueError if the passed operator is not implemented
                check_stats(stats=[operator], categorical=False)
                stats = [operator]
            # the passed operator can be also a function prototype (callable)
            elif callable(operator):
                add_stats = {operator.__name__: deepcopy(operator)}
            else:
                raise ValueError(
                    f"Could not pass {operator} to rasterstats.\n"
                    + "Please check the rasterstats docs how to pass user-defined statistics:\n"
                    + "https://pythonhosted.org/rasterstats/manual.html#user-defined-statistics"
                )

            # get raster values from EOdal band
            vals = self.values.copy()

            # check if data is masked array
            if self.is_masked_array:
                vals = vals.astype(float)
                vals = vals.filled(np.nan)

            # check no-data value. Rasterstats fails when nodata is nan
            # and the dtype of vals is int
            if issubclass(vals.dtype.type, np.integer) and np.isnan(self.nodata):
                vals = vals.astype(float)

            # call rasterstats.zonal_stats for the current operator
            res = zonal_stats(
                features,
                vals,
                affine=affine,
                stats=stats,
                add_stats=add_stats,
                nodata=self.nodata,
            )
            stats_operator_list.append(res)

        # combine the list of stats into a format consistent with the standard zonal_stats call
        _stats = []
        for idx in range(features.shape[0]):
            feature_stats = {}
            for odx, operator in enumerate(method):
                _operator = operator
                if callable(_operator):
                    _operator = _operator.__name__
                feature_operator_res = stats_operator_list[odx][idx][_operator]
                if not keep_nans:
                    try:
                        if np.isnan(feature_operator_res):
                            continue
                    except TypeError:
                        # rasterstats returns None instead of nan
                        if feature_operator_res is None:
                            continue
                feature_stats[_operator] = feature_operator_res
            # do not add features without statistics
            if len(feature_stats) == 0:
                continue
            # save the geometries and all other attributes of the feature(s) used
            feature_stats.update(features.iloc[idx].to_dict())
            feature_stats.update({"crs": features.crs})
            _stats.append(feature_stats)

        return _stats

    def scale_data(
        self,
        inplace: Optional[bool] = False,
        pixel_values_to_ignore: Optional[List[Union[int, float]]] = None,
    ):
        """
        Applies scale and offset factors to the data.

        :param inplace:
            if False (default) returns a copy of the ``Band`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :param pixel_values_to_ignore:
            optional list of pixel values (e.g., nodata values) to ignore,
            i.e., where scaling has no effect
        :returns:
            ``Band`` instance if `inplace` is False, None instead.
        """
        scale, offset = self.scale, self.offset
        if self.is_masked_array:
            if pixel_values_to_ignore is None:
                scaled_array = scale * (self.values.data + offset)
            else:
                scaled_array = self.values.data.copy().astype(float)
                scaled_array[~np.isin(scaled_array, pixel_values_to_ignore)] = scale * (
                    scaled_array[~np.isin(scaled_array, pixel_values_to_ignore)]
                    + offset
                )
            scaled_array = np.ma.MaskedArray(data=scaled_array, mask=self.values.mask)
        elif self.is_ndarray:
            if pixel_values_to_ignore is None:
                scaled_array = scale * (self.values + offset)
            else:
                scaled_array = self.values.copy().astype(float)
                scaled_array[~np.isin(scaled_array, pixel_values_to_ignore)] = scale * (
                    scaled_array[~np.isin(scaled_array, pixel_values_to_ignore)]
                    + offset
                )
        elif self.is_zarr:
            raise NotImplemented()

        if inplace:
            object.__setattr__(self, "values", scaled_array)
        else:
            attrs = deepcopy(self.__dict__)
            attrs.update({"values": scaled_array})
            return Band(**attrs)

    def to_dataframe(self) -> gpd.GeoDataFrame:
        """
        Returns a ``GeoDataFrame`` from the raster band data

        :returns:
            ``GeoDataFrame`` of raster values in the spatial coordinate
            system of the raster band data. The geometry type is always
            ``Point``.
        """
        # get coordinates of the first band in flattened format
        coords = self._flatten_coordinates()
        # get EPSG code
        epsg = self.geo_info.epsg

        # if the band is a masked array, we need numpy.ma functions
        new_shape = self.nrows * self.ncols
        if self.is_masked_array:
            flattened = np.ma.reshape(self.values, new_shape, order="F")
            # save mask to array
            mask = flattened.mask
            # compress array (removes masked values)
            flattened = flattened.compressed()
            # mask band coordinates
            for coord in coords:
                coord_masked = np.ma.MaskedArray(data=coords[coord], mask=mask)
                coord_compressed = coord_masked.compressed()
                coords.update({coord: coord_compressed})
        # otherwise we can use numpy ndarray's functions
        elif self.is_ndarray:
            flattened = np.reshape(self.values, new_shape, order="F")
        elif self.is_zarr:
            raise NotImplemented()

        # convert the coordinates to shapely geometries
        coordinate_geoms = [
            Point(c[0], c[1]) for c in list(zip(coords["x"], coords["y"]))
        ]
        # call the GeoDataFrame constructor
        gdf = gpd.GeoDataFrame(geometry=coordinate_geoms, crs=epsg)
        # add band data
        gdf[self.band_name] = flattened

        return gdf

    def to_xarray(self, attributes: Dict[str, Any] = {}, **kwargs) -> xr.DataArray:
        """
        Returns a ``xarray.Dataset`` from the raster band data
        (dime

        NOTE:
            To ensure consistency with ``xarray`` pixel coordinates are
            shifted from the upper left pixel corner to the center.

        :param attributes:
            additional raster attributes to update or add
        :param kwargs:
            additional key-word arguments to pass to `~xarray.Dataset`
        :return:
            ``xarray.DataArray`` with x and y coordinates. Raster attributes
            are preserved.
        """

        band_data = deepcopy(self.values)
        # masked pixels are set to nodata
        if self.is_masked_array:
            try:
                band_data.filled(self.nodata)
            # on type error cast to float since this is most likely caused
            # by a data type miss-match (int <-> float)
            except TypeError:
                band_data = band_data.astype(float)
                band_data.filled(self.nodata)
            except Exception as e:
                raise ValueError(f"Cannot set masked pixels to nodata: {e}")

        # get coordinates and shift them half a pixel size if the current
        # pixel coordinate model is Area (GDAL default) since xarray follows
        # the convention for NETCDF and expects Point coordinates
        coords = self.coordinates
        coords.update({"band": np.array([self.band_name], dtype=object)})
        if self.area_or_point == "Area":
            shift_x = 0.5 * self.geo_info.pixres_x
            shift_y = 0.5 * self.geo_info.pixres_y
            coords.update(
                {
                    "x": [val + shift_x for val in coords["x"]],
                    "y": [val + shift_y for val in coords["y"]],
                }
            )

        # define attributes
        attrs = self.get_attributes(**attributes)

        # call DataArray constructor
        new_shape = (1, band_data.shape[0], band_data.shape[1])
        xarr = xr.DataArray(
            data=band_data.reshape(new_shape),
            dims=("band", "y", "x"),
            coords=coords,
            attrs=attrs,
            **kwargs,
        )

        return xarr

    def to_rasterio(self, fpath_raster: Path, **kwargs) -> None:
        """
        Writes the band data to a raster dataset using ``rasterio``.

        :param fpath_raster:
            file-path to the raster dataset to create. The ``rasterio``
            driver is identified by the file-name extension. In case
            jp2 is selected, loss-less compression is carried out.
        :param kwargs:
            additional keyword arguments to append to metadata dictionary
            used by ``rasterio`` to write datasets
        """

        # check output file naming and driver
        try:
            driver = driver_from_extension(fpath_raster)
        except Exception as e:
            raise ValueError(
                "Could not determine GDAL driver for " f"{fpath_raster.name}: {e}"
            )

        # construct meta dictionary required by rasterio
        meta = self.get_meta(driver, **kwargs)

        # make sure JPEG compression is loss-less
        if driver == "JP2OpenJPEG":
            meta.update({"QUALITY": "100", "REVERSIBLE": "YES"})

        # open the result dataset and try to write the bands
        with rio.open(fpath_raster, "w+", **meta) as dst:
            # set band name
            dst.set_band_description(1, self.band_name)
            # write band data
            if self.is_masked_array:
                vals = self.values.data
                mask = self.values.mask
                vals[mask] = self.nodata
                dst.write(self.values, 1)
            elif self.is_ndarray:
                dst.write(self.values, 1)
