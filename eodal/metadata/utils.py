"""
Helper functions to interact with the satellite meta data base

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
import subprocess
import pandas as pd

from pathlib import Path
from typing import Optional
from typing import Union

from eodal.utils.exceptions import DataNotFoundError


def _check_linux_cifs(ip: Union[str, Path]) -> Path:
    """
    Searches for mount point of an external file system on a Linux
    operating system

    :ip:
        IP or network address of the NAS device for which
        to search the mount point.
    """

    res = Path("")

    exe = "cat /proc/mounts | grep cifs"
    response = subprocess.getoutput(exe)
    lines = response.split("\n")
    for line in lines:
        if str(ip) in line:
            # data is on mounted share -> get local file system mapper
            local_path = line.split(" ")[1]
            # check if current user has access to read local path, otherwise keep
            # searching (might happen if another user manually mounts the NAS)
            if os.access(local_path, os.R_OK):
                res = Path(local_path)
                break

    return res


def reconstruct_path(
    record: pd.Series,
    is_raw_data: Optional[bool] = True,
    path_to_nas: Optional[bool] = True,
) -> Path:
    """
    auxiliary function to reconstruct the actual dataset location
    based on the entries in the metatdata base. Raises an error
    if the dataset was not found.

    :param record:
        single record from the metadata base denoting a single dataset
    :param is_raw_data:
        if True (default) assumes the queried data is Sentinel-2 ESA
        derived "raw" data in .SAFE archive format and not already processed
        by eodal to multi-band geoTiff files.
    :param path_to_nas:
        if True (default) tries to find the mount point of the NAS file system
        on the local machine's file system.
    :return in_dir:
        filepath to the directory for the local machine
    """

    ip = Path(record.storage_device_ip)

    # check if ip points towards a network drive under Linux
    if path_to_nas:
        if os.name == "posix":
            # search for mount point of NAS file system
            mount_point = _check_linux_cifs(ip=ip)

            # if this attempt failed, we can check the alias if available
            if str(mount_point) == "." and record.storage_device_ip_alias != "":
                mount_point = _check_linux_cifs(ip=record.storage_device_ip_alias)

            # if no mount point is found raise an error
            if str(mount_point) == "":
                raise DataNotFoundError(
                    "Could not find mount point for external file system"
                )

            share = mount_point.joinpath(record.storage_share)

        # Windows does not know about mount points, it should be able to work with network paths
        elif os.name == "nt":
            share = Path(record.storage_device_ip).joinpath(record.storage_share)
            # if share is not available test alias if available
            if not share.exists():
                if record.storage_device_ip_alias == "":
                    raise DataNotFoundError(
                        "Could not find network path for external file system"
                    )

                share = Path(record.storage_device_ip.alias).joinpath(
                    record.storage_share
                )

    # path is to local filesystem or does not require mount points
    else:
        share = Path(record.storage_share)

    # the path should work 'as it is' on Windows machines by replacing the slashes
    if os.name == "nt":
        # TODO test on Windows
        tmp = str(share)
        tmp = tmp.replace(r"//", r"\\").replace(r"/", os.sep)
        share = Path(tmp)

    if not share.exists():
        raise DataNotFoundError(f"Could not find {share}")

    if is_raw_data:
        in_dir = share.joinpath(record.product_uri)
    else:
        in_dir = share

    # handle products not ending with '.SAFE' (e.g., when data comes from Mundi)
    if not in_dir.exists():
        in_dir = Path(str(in_dir).replace(".SAFE", ""))

        if not in_dir.exists():
            raise NotADirectoryError(f"Could not find {str(in_dir)}")

    return in_dir
