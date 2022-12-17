'''
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
'''

from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from sqlalchemy.exc import DatabaseError
from shapely.geometry import box
from typing import List, Optional

from eodal.config import get_settings
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.metadata.database.querying import find_raw_data_by_bbox
from eodal.utils.constants import ProcessingLevels
from eodal.utils.exceptions import STACError

settings = get_settings()

class MapperConfigs:
    """
    global configurations of the Mapper class defining metadata search
    criteria (space and time), data collections to search and behavior
    for bringing data into analysis-ready-format (ARD)

    :attrib collection:
        name of the collection (<platform>-<sensor>-<processing level>) to use.
        E.g., "Sentinel2-MSI-L2A
    :attrib feature:
        geographic feature(s) for which to extract data from collection
    :atrrib time_start:
        time stamp from which onwards to extract data from collection
    :atrrib time_end:
        time stamp till which to extract data from collection
    :attrib metadata_filters:
        list of custom metadata filters to shrink collection to.
        Examples include cloud cover filters in the case of optical data
        or filter by incidence angle in the case of SAR observations.
    """
    def __init__(
        self,
        collection: str,
        feature: Feature,
        time_start: datetime,
        time_end: datetime,
        metadata_filters: Optional[List[Filter]] = None
    ):
        """
        default class constructor

        :param collection:
            name of the collection (<platform>-<sensor>) to use.
            E.g., "sentinel2-msi". <sensor> is optional and can be omitted
            if a platform does not carry more than a single sensor. I.e.,
            one could also pass "sentinel2" instead.
        :param feature:
            geographic feature(s) for which to extract data from collection
        :param time_start:
            time stamp from which onwards to extract data from collection
        :param time_end:
            time stamp till which to extract data from collection
        :param  metadata_filters:
            list of custom metadata filters to shrink collection to.
            Examples include cloud cover filters in the case of optical data
            or filter by incidence angle in the case of SAR observations.
        """
        # check inputs
        if not isinstance(collection, str):
            raise TypeError('Collection must be a string')

        if len(collection) < 3:
            raise ValueError('Collections must have at least 3 characters')
        if collection.count('-') > 2:
            raise ValueError(
                f'Collections must obey the format <platform>-<sensor> where <sesor> is optional'
            )
        if not isinstance(feature, Feature):
            raise TypeError('Expected a Feature object')
        if not isinstance(time_start, datetime) and not isinstance(time_end, datetime):
            raise TypeError('Expected datetime objects')
        if metadata_filters is not None:
            if not np.array([isinstance(x, Filter) for x in metadata_filters]).all():
                raise TypeError('All filters must be instances of the Filter class')

        self._collection = collection
        self._feature = feature
        self._time_start = time_start
        self._time_end = time_end
        self._metadata_filters = metadata_filters

    def __repr__(self) -> str:
        return f'EOdal MapperConfig\n------------------\nCollection: {self.collection}' + \
            f'\nTime Range: {self.time_start} - {self.time_end}\nFeature:\n' + \
            f'{self.feature.__repr__()}\nMetadata Filters: {str(self.metadata_filters)}'

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def platform(self) -> str:
        return self.collection.split('-')[0]

    @property
    def sensor(self) -> str:
        try:
            return self._collection.split('-')[1]
        except IndexError:
            return ''

    @property
    def feature(self) -> Feature:
        return self._feature

    @property
    def time_start(self) -> datetime:
        return self._time_start

    @property
    def time_end(self) -> datetime:
        return self._time_end

    @property
    def metadata_filters(self) -> List[Filter] | None:
        return self._metadata_filters

    @classmethod
    def from_yaml(cls, fpath: str | Path):
        """
        Load mapping configurations from YAML file
        """
        with open(fpath, 'r') as f:
            try:
                yaml_content = yaml.safe_load(f)   
            except yaml.YAMLError as exc:
                print(exc)
        # reconstruct the Featue object first
        if 'feature' not in yaml_content.keys():
            raise ValueError('"feature" attribute is required"')
        feature_yaml = yaml_content['feature']
        # reconstruct the filter objects
        filter_list = []
        if 'metadata_filters' in yaml_content.keys():
            filters_yaml = yaml_content['metadata_filters']
            for filter_yaml in filters_yaml:
                filter_list.append(Filter(*filter_yaml.split()))
        try:
            feature = Feature.from_dict(feature_yaml)
            return cls(
                collection=yaml_content['collection'],
                feature=feature,
                time_start=yaml_content['time_start'],
                time_end=yaml_content['time_end'],
                metadata_filters=filter_list
            )
        except KeyError as e:
            raise ValueError(f'IMissing keys in yaml file: {e}')

    def to_yaml(self, fpath: str | Path) -> None:
        """
        save MapperConfig to YAML file (*.yml)

        :param fpath:
            file-path where saving the Feature instance to
        """
        mapper_configs_dict = {}
        mapper_configs_dict['collection'] = self.collection
        mapper_configs_dict['feature'] = self.feature.to_dict()
        mapper_configs_dict['time_start'] = self.time_start
        mapper_configs_dict['time_end'] = self.time_end
        mapper_configs_dict['metadata_filters'] = [x.__repr__() for x in self.metadata_filters]
        with open(fpath, 'w+') as f:
            yaml.dump(mapper_configs_dict, f, allow_unicode=True)

class Mapper:
    """
    Generic class for mapping Earth Observation Data across space and time
    and bring them into Analysis-Readay-Format (ARD).

    The mapper class takes over searching for EO scenes, merging them and
    filling eventually occurring black-fill (no-data regions).

    :attrib mapper_configs:
        `MapperConfig` instance defining search criteria
    """

    def __init__(self, mapper_configs: MapperConfigs):
        """
        Class constructor

        :param mapper_configs:
            `MapperConfig` instance defining search criteria
        """
        if not isinstance(mapper_configs, MapperConfigs):
            raise TypeError(f'Expected a MapperConfigs instance')
        self._mapper_configs = mapper_configs
        self._observations = None

    def __repr__(self) -> str:
        return f'EOdal Mapper\n============\n{self.mapper_configs.__repr__()}'

    @property
    def mapper_configs(self) -> MapperConfigs:
        """mapper configurations"""
        return self._mapper_configs

    @property
    def observations(self) -> None | pd.DataFrame:
        """scene metadata found"""
        return self._observations

    @observations.setter
    def observations(self, values: Optional[pd.DataFrame]):
        """set scene metadata"""
        self._observations = deepcopy(values)

    def get_scenes(self):
        """
        Query available scenes for the current `MapperConfigs`.
        This method only queries a metadata catalog without reading data.
        """
        # TODO: handle point geometries

        # determine bounding box of the feature using
        # its representation in geographic coordinates
        feature_wgs84 = self.mapper_configs.feature.to_epsg(4326)
        bbox = box(*feature_wgs84.geometry.bounds)

        # determine platform
        platform = self.mapper_configs.platform

        # put everything together
        kwargs = {
            'platform': platform,
            'time_start': self.mapper_configs.time_start,
            'time_end': self.mapper_configs.time_end,
            'bounding_box': bbox,
            'metadata_filters': self.mapper_configs.metadata_filters
        }

        # query the metadata catalog
        if settings.USE_STAC:
            try:
                exec(f'from eodal.metadata.stac import {platform}')
                scenes_df = eval(f'{platform}(**kwargs)')
            except Exception as e:
                raise STACError(f"Querying STAC catalog failed: {e}")
        else:
            try:
                scenes_df = find_raw_data_by_bbox(**kwargs)
            except Exception as e:
                raise DatabaseError(f"Querying metadata DB failed: {e}")

        self.observations = scenes_df
    






    