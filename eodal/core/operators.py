"""
Base class defining map algebra operators

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

from typing import List


class Operator:
    """
    Band operator supporting basic algebraic operations
    """

    operators: List[str] = ["+", "-", "*", "/", "**", "<", ">", "==", "<=", ">=", "!="]

    class BandMathError(Exception):
        pass

    @classmethod
    def check_operator(cls, operator: str) -> None:
        """
        Checks if the operator passed is valid

        :param operator:
            passed operator to evaluate
        """
        # check operator passed first
        if operator not in cls.operators:
            raise ValueError(f'Unknown operator "{operator}"')

    @classmethod
    def calc(cls):
        """
        Class method to be overwritten by inheriting class
        """
        pass
