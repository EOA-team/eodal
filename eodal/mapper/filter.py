'''
Predefined filters for EO data selection by metadata.

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

class Filter:
    """
    The generic filter class.

    :attrib entity:
        metadata entity to use for filtering
    :attrib condition:
        condition that must be met to keep a metadata item in the
        selection
    """
    def __init__(self, entity: str, condition: str):
        """
        Constructor method

        :param entity:
            metadata entity to use for filtering
        :param condition:
            condition that must be met to keep a metadata item in the
            selection
        """
        # check inputs
        if not isinstance(entity, str):
            raise TypeError('Entity argument must be a string')
        if entity == '':
            raise ValueError('Entity argument must not be an empty string')
        if not isinstance(condition, str):
            raise TypeError('Condition argument must be a string')
        if condition == '':
            raise ValueError('Condition argument must not be an empty string')

        self._entity = entity
        self._condition = condition

    def __repr__(self) -> str:
        return self.expression

    @property
    def entity(self) -> str:
        """metadata entity used to filter"""
        return self._entity

    @property
    def condition(self) -> str:
        """filter condition"""
        return self._condition

    @property
    def expression(self) -> str:
        """returns the filter expression as string"""
        return f'{self.entity} {self.condition}'
