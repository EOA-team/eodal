"""
Collection of exceptions raised by eodal's modules

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


class NotProjectedError(Exception):
    pass


class ResamplingFailedError(Exception):
    pass


class BandNotFoundError(Exception):
    pass


class UnknownProcessingLevel(Exception):
    pass


class InputError(Exception):
    pass


class DataNotFoundError(Exception):
    pass


class ArchiveNotFoundError(Exception):
    pass


class MetadataNotFoundError(Exception):
    pass


class RegionNotFoundError(Exception):
    pass


class ArchiveCreationError(Exception):
    pass


class BlackFillOnlyError(Exception):
    pass


class ReprojectionError(Exception):
    pass


class DataExtractionError(Exception):
    pass


class STACError(Exception):
    pass


class APIError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class SceneNotFoundError(Exception):
    pass
