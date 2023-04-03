"""
Helper functions for the downloader package.

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

import os
import glob
import subprocess
from pathlib import Path
from typing import Optional

from eodal.config import get_settings
from eodal.utils.exceptions import DataNotFoundError

Settings = get_settings()
logger = Settings.logger


def unzip_datasets(
    download_dir: Path, platform: str, remove_zips: Optional[bool] = True
) -> None:
    """
    Helper function to unzip Sentinel-1 and 2 mapper once they are
    downloaded from CREODIAS. Works currently on  *nix system only and requires
    `unzip` to be installed on the system.

    :param download_dir:
        directory where the zipped mapper in .SAFE format are located
    :param platform:
        either 'S1' (Sentinel-1) or 'S2' (Sentinel-2)
    :param remove_zips:
        If set to False the zipped .SAFE mapper will be kept, otherwise
        (Default) they will be removed
    """

    # find zipped .SAFE archives
    dot_safe_zips = glob.glob(download_dir.joinpath(f"{platform}*.zip").as_posix())
    n_zips = len(dot_safe_zips)
    if n_zips == 0:
        raise DataNotFoundError(
            f'Could not find any zips for platform "{platform}" in {download_dir}'
        )

    # change into the donwload directory
    current_dir = os.getcwd()

    # use unzip in subprocess call to unpack the zip files
    for idx, dot_safe_zip in enumerate(dot_safe_zips):
        os.chdir(download_dir)
        arg_list = ["unzip", "-n", Path(dot_safe_zip).name]
        process = subprocess.Popen(
            arg_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, _ = process.communicate()

        logger.info(f"Unzipped {dot_safe_zip} ({idx+1}/{n_zips})")

        os.chdir(current_dir)
        if remove_zips:
            os.remove(dot_safe_zip)
