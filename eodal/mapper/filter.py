"""
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
"""

from __future__ import annotations

from typing import Any

operators = ["<", "<=", "==", "!=", ">", ">="]


class Filter:
    """
    The generic filter class. A filter is used to query data catalogs.

    Each filter follows the following structure:

    <entity> <operator> <value>

    For instance, `cloudy_pixel_percentage < 10`, where

        * `cloudy_pixel_percentage` is the entity to filter
        * `<` is the operator
        * `10` is the value

    :attrib entity:
        metadata entity to use for filtering
    :attrib operator:
            comparison operator to use, e.g., "gt" for "greater than" (>)
    :attrib value:
        value on the right-hand side of the filter expression
    """

    def __init__(self, entity: str, operator: str, value: Any):
        """
        Constructor method

        :param entity:
            metadata entity to use for filtering
        :param operator:
            comparison operator to use, e.g., ">" for "greater than" (value)
        :param value:
            value on the right-hand side of the filter expression
        """
        # check inputs
        if not isinstance(entity, str):
            raise TypeError("Entity argument must be a string")
        if entity == "":
            raise ValueError("Entity argument must not be an empty string")
        if not isinstance(operator, str):
            raise TypeError("Operator argument must be a string")
        if operator not in operators:
            raise ValueError("Operator must be one of: " + ",".join(operators))
        if value is None:
            raise ValueError("Value cannot be None")

        self._entity = entity
        self._operator = operator
        self._value = value

    def __repr__(self) -> str:
        return self.expression

    @property
    def entity(self) -> str:
        """metadata entity used to filter"""
        return self._entity

    @property
    def operator(self) -> str:
        """filter operator"""
        return self._operator

    @property
    def value(self) -> Any:
        """right-side value of the filter"""
        return self._value

    @property
    def expression(self) -> str:
        """returns the filter expression as string"""
        return f"{self.entity} {self.operator} {self.value}"
