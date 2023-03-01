'''
Tests for the filter class.

.. versionadded:: 0.1.1

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

import pytest

from eodal.mapper.filter import Filter

def test_filter():
    # filter by cloud cover
    cc_filter = Filter(entity='cloudy_pixel_percentage', operator='<', value=30)
    assert cc_filter.expression == 'cloudy_pixel_percentage < 30'
    assert cc_filter.entity == 'cloudy_pixel_percentage'
    assert cc_filter.operator == '<'
    assert cc_filter.value == 30

    # wrong data types
    with pytest.raises(ValueError):
        cc_filter = Filter(entity='cloudy_pixel_percentage', operator='lt', value=30)
    with pytest.raises(TypeError):
        cc_filter = Filter(entity=4, operator='<', value=30)

    # passing None
    with pytest.raises(ValueError):
        cc_filter = Filter(entity='cloudy_pixel_percentage', operator='<', value=None)
