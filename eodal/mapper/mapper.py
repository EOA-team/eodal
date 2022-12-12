'''
Created on Dec 12, 2022

@author: graflu
'''

from datetime import datetime

from eodal.mapper.features import Feature
from eodal.mapper.filters import Filter

from typing import List, Optional

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


class Mapper:
    """
    Generic class for mapping Earth Observation Data across space and time
    and bring them into Analysis-Readay-Format (ARD).

    The mapper class takes over searching for EO scenes, merging them and
    filling eventually occurring black-fill (no-data regions).
    """

    def __init__(self, mapper_configs: Mapper_Configs):