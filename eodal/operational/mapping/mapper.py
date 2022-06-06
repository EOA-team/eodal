"""
Generic mapping module

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

import cv2
from datetime import date
from geopandas import GeoDataFrame
from pandas import DataFrame
from pathlib import Path
from shapely.geometry import MultiPolygon
from shapely.geometry import Point
from shapely.geometry import Polygon
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


class Feature(object):
    """
    Class representing a feature, e.g., an area of interest.

    :attrib identifier:
        unique identifier of the feature
    :attrib geom:
        geometry of the feature
    :attrib epsg:
        epsg code of the feature's geometry
    :attrib properties:
        any key-value dictionary like mapping of feature properties
        (e.g., its name or other attributes spoken in terms of an
        ESRI shapefile's table of attributes)
    """

    def __init__(
        self,
        identifier: Any,
        geom: Union[Point, Polygon, MultiPolygon],
        epsg: int,
        properties: Optional[Dict[str, Any]],
    ):
        """
        Initializes a new ``Feature`` instance.

        :param identifier:
            unique identifier of the feature
        :param geom:
            geometry of the feature
        :param epsg:
            epsg code of the feature's geometry
        :param properties:
            any key-value dictionary like mapping of feature properties
            (e.g., its name or other attributes spoken in terms of an
            ESRI shapefile's table of attributes)
        """
        # some checks
        if epsg <= 0:
            raise TypeError("EPSG codes must be >= 0")
        if not hasattr(geom, "__geo_interface__"):
            raise TypeError("Geometries must implement the __geo_interface__")
        if not isinstance(properties, dict):
            raise TypeError("Only dictionary are accepted")

        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "geom", geom)
        object.__setattr__(self, "epsg", epsg)
        object.__setattr__(self, "properties", properties)

    def __setattr__(self, *args):
        raise TypeError("Feature attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("Feature attributes are immutable")

    def __repr__(self):
        return str(self.__dict__)

    def to_gdf(self) -> GeoDataFrame:
        """
        Returns the feature as ``GeoDataFrame``

        :returns:
            ``Feature`` instance as ``GeoDataFrame``
        """
        self.properties.update({"epsg": self.epsg})
        return GeoDataFrame(
            self.properties,
            index=[self.identifier],
            crs=f"epsg:{self.epsg}",
            geometry=[self.geom],
        )


class MapperConfigs(object):
    """
    Class defining configurations for the ``Mapper`` class

    :attrib band_names:
        names of raster bands to process from each dataset found during the
        mapping process
    :attrib resampling_method:
        resampling might become necessary when the spatial resolution
        changes. Nearest neighbor by default.
    :attrib spatial_resolution:
        if provided brings all raster bands into the same spatial resolution
    :attrib reducers:
        optional list of spatial reducers (e.g., 'mean') converting all
        raster observations from 2d arrays to scalars.
    :atrrib tile_selection:
        optional selection of tile ids for sensors following a tiling scheme
        (e.g., S2 tiles, or Landsat PathRows).
    """

    def __init__(
        self,
        band_names: Optional[List[str]] = None,
        resampling_method: Optional[int] = cv2.INTER_NEAREST_EXACT,
        spatial_resolution: Optional[Union[int, float]] = 10.0,
        reducers: Optional[List[str]] = None,
        tile_selection: Optional[List[str]] = None,
    ):
        """
        Constructs a new ``MapperConfig`` instance.

        :param band_names:
            names of raster bands to process from each dataset found during the
            mapping process
        :param resampling_method:
            resampling might become necessary when the spatial resolution
            changes. Nearest neighbor by default.
        :param spatial_resolution:
            if provided brings all raster bands into the same spatial resolution
        :param reducers:
            optional list of spatial reducers (e.g., 'mean') converting all
            raster observations from 2d arrays to scalars.
        """
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "resampling_method", resampling_method)
        object.__setattr__(self, "spatial_resolution", spatial_resolution)
        object.__setattr__(self, "reducers", reducers)
        object.__setattr__(self, "tile_selection", tile_selection)

    def __setattr__(self, *args):
        raise TypeError("MapperConfigs attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("MapperConfigs attributes are immutable")

    def __repr__(self):
        return str(self.__dict__)


class Mapper(object):
    """
    Generic Mapping class to extract raster data for a selection of areas of interest
    (AOIs) and time period.

    :attrib date_start:
        start date of the time period to consider (inclusive)
    :attrib date_end:
        end date of the time period to consider (inclusive)
    :attrib feature_collection:
        ``GeoDataFrame`` or any vector file understood by ``fiona`` with
        geometries of type ``Point``, ``Polygon`` or ``MultiPolygon``
        defining the Areas Of Interest (AOIs) to extract (e.g., agricultural
        field parcels). Each feature in the collection will be processed
        separately
    :attrib unique_id_attribute:
        attribute in the `polygon_features`'s attribute table making each
        feature (AOI) uniquely identifiable. If None (default) the features
        are labelled by a unique-identifier created on the fly.
    :attrib mapping_configs:
        Mapping configurations specified by `~eodal.operational.mapping.MapperConfigs`.
        Uses default configurations if not provided.
    :attrib observations:
        data structure for storing DB query results per AOI.
    """

    def __init__(
        self,
        date_start: date,
        date_end: date,
        feature_collection: Union[Path, GeoDataFrame],
        unique_id_attribute: Optional[str] = None,
        mapper_configs: MapperConfigs = MapperConfigs(),
    ):
        """
        Constructs a new ``Mapper`` instance.

        :param date_start:
            start date of the time period to consider (inclusive)
        :param date_end:
            end date of the time period to consider (inclusive)
        :param feature_collection:
            ``GeoDataFrame`` or any vector file understood by ``fiona`` with
            geometries of type ``Point``, ``Polygon`` or ``MultiPolygon``
            defining the Areas Of Interest (AOIs) to extract (e.g., agricultural
            field parcels). Each feature in the collection will be processed
            separately
        :param unique_id_attribute:
            attribute in the `polygon_features`'s attribute table making each
            feature (AOI) uniquely identifiable. If None (default) the features
            are labelled by a unique-identifier created on the fly.
        :param mapping_configs:
            Mapping configurations specified by `~eodal.operational.mapping.MapperConfigs`.
            Uses default configurations if not provided.
        """
        object.__setattr__(self, "date_start", date_start)
        object.__setattr__(self, "date_end", date_end)
        object.__setattr__(self, "feature_collection", feature_collection)
        object.__setattr__(self, "unique_id_attribute", unique_id_attribute)
        object.__setattr__(self, "mapper_configs", mapper_configs)

        observations: Dict[str, DataFrame] = None
        object.__setattr__(self, "observations", observations)

        features: Dict[str, Feature] = None
        object.__setattr__(self, "features", features)

    def __setattr__(self, *args):
        raise TypeError("Mapper attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("Mapper attributes are immutable")

    def get_feature_ids(self) -> List:
        """
        Lists feature identifiers in feature collection

        :returns:
            list of feature identifiers
        """
        if isinstance(self.feature_collection, Path):
            return []
        return [x["id"] for x in self.feature_collection["features"]]

    def get_feature(self, feature_id: Any) -> Dict[str, Any]:
        """
        Returns a feature in its ``__geo_interface__`` representation
        out of the feature collection

        :param feature_id:
            feature identifier to use for extraction
        :param as_gdf:
            return feature as dictionary (default) or ``GeoDataFrame``?
        :returns:
            the feature with its properties and geometry
        """
        if isinstance(self.feature_collection, Path):
            return {}
        if isinstance(self.feature_collection, GeoDataFrame):
            gdf = self.feature_collection[
                self.feature_collection[self.unique_id_attribute] == feature_id
            ]
            return {} if gdf.empty else gdf.__geo_interface__
        else:
            res = [
                x for x in self.feature_collection["features"] if x["id"] == feature_id
            ]
            if len(res) == 0:
                raise KeyError(f'No feature found with ID "{feature_id}"')
            return {"type": "FeatureCollection", "features": res}

    def get_scenes(self):
        """
        Method to query available scenes. To be implemented by sensor-specific
        classes inheriting from the generic mapper class.
        """
        pass

    def get_feature_scenes(self, feature_identifier: Any) -> DataFrame:
        """
        Returns a ``DataFrame`` with all scenes found for a
        feature in the feature collection

        NOTE:
            The scene count is termed ``raw_scene_count``. This
            highlights that the final scene count might be
            different due to orbit and spatial design pattern.

        :param feature_identifier:
            unique identifier of the aoi. Must be the same identifier
            used during the database query
        :returns:
            ``DataFrame`` with all scenes found for a given
            set of search parameters
        """
        try:
            return self.observations[feature_identifier].copy()
        except Exception as e:
            raise KeyError(f"{feature_identifier} did not return any results: {e}")
