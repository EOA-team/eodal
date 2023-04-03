"""
Sentinel-1 specific helper functions to interact with datasets organized
in .SAFE structure.

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

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

from eodal.config import get_settings

Settings = get_settings()


def _url_to_safe_name(stac_asset: str | Dict[str, Any]) -> str:
    """
    extracts the .SAFE name from the asset returned by the STAC query

    :param url:
        asset containing hyperlink reference to Sentinel-1 dataset
    :returns:
        .SAFE dataset name extracted from the URL of the vh polarization
    """
    if isinstance(stac_asset, dict):
        stac_asset = stac_asset["vh"]["href"]
    url_parts = stac_asset.split("/")
    dot_safe_name = [x for x in url_parts if x.startswith("S1")][0]
    return dot_safe_name


def get_S1_acquistion_time_from_safe(dot_safe_name: Path | Dict[str, Any]) -> date:
    """
    Determines the image acquisition time of a dataset in .SAFE format
    based on the file naming

    :param dot_safe_name:
        name of the .SAFE dataset
    :return:
        image acquistion time (full timestamp)
    """
    if isinstance(dot_safe_name, Path):
        dot_safe_name = dot_safe_name.name
    elif Settings.USE_STAC:
        dot_safe_name = _url_to_safe_name(dot_safe_name)

    return datetime.strptime(dot_safe_name.split("_")[4], "%Y%m%dT%H%M%S")


def get_S1_platform_from_safe(dot_safe_name: Path | Dict[str, str]) -> str:
    """
    Get the platform information from a .SAFE archive

    :param dot_safe_name:
        file-path to .SAFE archive or asset item returned from STAC
    :returns:
        satellite platform (e.g., S1A for Sentinel-1A)
    """
    if isinstance(dot_safe_name, Path):
        dot_safe_name = dot_safe_name.name
    elif Settings.USE_STAC:
        dot_safe_name = _url_to_safe_name(dot_safe_name)

    return dot_safe_name.split("_")[0]


def get_s1_imaging_mode_from_safe(dot_safe_name: Path | Dict[str, str]) -> str:
    """
    Get the imaging mode information from a Sentinel-1 .SAFE archive

    :param dot_safe_name:
        file-path to .SAFE archive or asset item returned from STAC
    :returns:
        imaging mode (e.g., IW for interferometric wide-swath)
    """
    if isinstance(dot_safe_name, Path):
        dot_safe_name = dot_safe_name.name
    elif Settings.USE_STAC:
        dot_safe_name = _url_to_safe_name(dot_safe_name)

    return dot_safe_name.split("_")[1]
