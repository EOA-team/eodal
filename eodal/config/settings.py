"""
Global *eodal* settings defining access to metadata DB (`eodal.operational`
modules, only), CREODIAS (optional), Copernicus (optional) and some package-wide
file and directory naming defaults. In addition, the module exposes a `logger` object
for package wide-logging (console and file output).

The ``Settings`` class uses ``pydantic``. This means all attributes of the class can
be **overwritten** using environmental variables or a `.env` file.

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

import logging
import tempfile

from datetime import datetime
from functools import lru_cache
from os.path import join
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Any

from .stac_providers import STAC_Providers


class Settings(BaseSettings):
    """
    The eodal setting class. Allows to modify default
    settings and behavior of the package using a .env file
    or environmental variables
    """

    # define DHUS username and password
    DHUS_USER: str = ""
    DHUS_PASSWORD: str = ""

    # define CREODIAS username and password
    CREODIAS_USER: str = ""
    CREODIAS_PASSWORD: str = ""
    # maximum number of records per request: 2000 (CREODIAS currently does not allow
    # more)
    CREODIAS_MAX_RECORDS: int = 2000

    # define Planet-API token
    PLANET_API_KEY: str = ""
    # Planet API URLs
    ORDERS_URL: str = "https://api.planet.com/compute/ops/orders/v2"
    DATA_URL: str = "https://api.planet.com/data/v1"

    # metadata base connection details
    DB_USER: str = "postgres"
    DB_PW: str = "P@ssW0rd!"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "metadata_db"

    DEFAULT_SCHEMA: str = "cs_sat_s1"
    ECHO_DB: bool = False

    # STAC configuration
    USE_STAC: bool = True
    MAX_ITEMS: int = 500
    LIMIT_ITEMS: int = 5

    # change the value of this variable to use a different STAC service provider
    STAC_BACKEND: Any = STAC_Providers.MSPC  # STAC_Providers.AWS

    # subscription key for MS-PC (might be required for some data sets like Sentinel-1)
    PC_SDK_SUBSCRIPTION_KEY: str = ""

    # path to custom CA_BUNDLE when calling the pystac_client behind a proxy server
    # when a path a custom certificate is required set this variable to a path
    STAC_API_IO_CA_BUNDLE: bool = True

    # maximum number of HTTPS retries
    NUMBER_HTTPS_RETRIES: int = 5

    # define logger
    CURRENT_TIME: str = datetime.now().strftime("%Y%m%d-%H%M%S")
    LOGGER_NAME: str = "eodal"
    LOG_FORMAT: str = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"
    LOG_DIR: str = str(Path.home())  # ..versionadd:: 0.2.1
    LOG_FILE: str = join(LOG_DIR, f"{CURRENT_TIME}_{LOGGER_NAME}.log")
    LOGGING_LEVEL: int = logging.INFO

    # temporary working directory
    TEMP_WORKING_DIR: Path = Path(tempfile.gettempdir())

    # logger
    logger: logging.Logger = logging.getLogger(LOGGER_NAME)

    def get_logger(self):
        """
        returns a logger object with stream and file handler
        """
        self.logger.setLevel(self.LOGGING_LEVEL)
        # create file handler which logs even debug messages
        fh: logging.FileHandler = logging.FileHandler(self.LOG_FILE)
        fh.setLevel(self.LOGGING_LEVEL)
        # create console handler with a higher log level
        ch: logging.StreamHandler = logging.StreamHandler()
        ch.setLevel(self.LOGGING_LEVEL)
        # create formatter and add it to the handlers
        formatter: logging.Formatter = logging.Formatter(self.LOG_FORMAT)
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)


@lru_cache()
def get_settings():
    """
    loads package settings using ``last-recently-used`` cache
    """
    s = Settings()
    s.get_logger()
    return s
