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
        self._entity = entity
        self._condition = condition

    def __repr__(self) -> str:
        return f'Filter by {self.entity} {self.condition}'

    @property
    def entity(self) -> str:
        return self._entity

    @property
    def condition(self) -> str:
        return self._condition

if __name__ == '__main__':
    
    cc_filter = Filter(entity='cloudy_pixel_percentage', condition='<30')
    cc_filter
    