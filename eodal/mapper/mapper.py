'''
Created on Dec 12, 2022

@author: graflu
'''

from __future__ import annotations

import yaml

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter

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
            name of the collection (<platform>-<sensor>-<processing level>) to use.
            E.g., "Sentinel2-MSI-L2A
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
        if len(collection) < 6:
            raise ValueError('Collections must have at least six characters')
        if collection.count('-') != 2:
            raise ValueError(
                f'Collections must obey the format <platform>-<sensor>-<prcoessing_level>'
            )
        if not isinstance(feature, Feature):
            raise TypeError('Expected a Feature object')
        if not isinstance(time_start, datetime) and not isinstance(time_end, datetime):
            raise TypeError('Expected datetime objects')
        if metadata_filters is not None:
            if not [isinstance(x, Filter) for x in metadata_filters].all():
                raise TypeError('All filters must be instances of the Filter class')

        self._collection = collection
        self._feature = feature
        self._time_start = time_start
        self._time_end = time_end
        self._metadata_filters = metadata_filters

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def platform(self) -> str:
        return self.collection.split('-')[0]

    @property
    def sensor(self) -> str:
        return self._collection.split('-')[1]

    @property
    def processing_level(self) -> str:
        return self._collection.split('-')[-1]

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
        try:
            feature = Feature.from_dict(feature_yaml)
            return cls(
                collection=yaml_content['collection'],
                feature=feature,
                time_start=yaml_content['time_start'],
                time_end=yaml_content['time_end'],
                metadata_filters=yaml_content['metadata_filters']
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
        mapper_configs_dict['metadata_filters'] = self.metadata_filters
        with open(fpath, 'w+') as f:
            yaml.dump(mapper_configs_dict, f, allow_unicode=True)

class Mapper:
    """
    Generic class for mapping Earth Observation Data across space and time
    and bring them into Analysis-Readay-Format (ARD).

    The mapper class takes over searching for EO scenes, merging them and
    filling eventually occurring black-fill (no-data regions).
    """

    def __init__(self, mapper_configs: MapperConfigs):
        pass
    
if __name__ == '__main__':

    from shapely.geometry import Point

    collection = 'sentinel2-msi-l2a'
    geom = Point([49,11])
    epsg = 4326
    name = 'Test Point'
    attributes = {'this': 'is a test', 'a': 123}
    feature = Feature(name, geom, epsg, attributes)
    time_start = datetime(2022,12,1)
    time_end = datetime.now()

    mapper_configs = MapperConfigs(collection, feature, time_start, time_end)
    fpath = '/mnt/ides/Lukas/test.yml'
    mapper_configs.to_yaml(fpath)

    mapper_configs_rl = MapperConfigs.from_yaml(fpath)
    assert mapper_configs.feature.name == mapper_configs_rl.feature.name, 'wrong feature name'
    assert mapper_configs.feature.epsg == mapper_configs_rl.feature.epsg, 'wrong feature EPSG'
    assert mapper_configs.feature.geometry == mapper_configs_rl.feature.geometry, 'wrong feature geometry'
    assert set(mapper_configs.feature.attributes) == set(mapper_configs_rl.feature.attributes), \
        'wrong feature attributes'
    assert mapper_configs.time_start == mapper_configs_rl.time_start, 'wrong start time'
    assert mapper_configs.time_end == mapper_configs_rl.time_end, 'wrong end time'
    assert mapper_configs.collection == mapper_configs_rl.collection, 'wrong collection'
        