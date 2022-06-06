"""
This function is part of the eodal's Sentinel-2 default processing chain.

It allows for spatial resampling of Sentinel-2 images to bring
the 10 and 20m spectral bands into either 10m (default) or 20m spatial resolution.
The function works on the full extent of a Sentinel-2 scene and writes
the output bands into a single multi-band geoTiff file.

For resampling spatial subsets of a scene which are considerably smaller than
the spatial extent of Sentinel-2 scene (almost 110km by 110km) consider using
``eodal.core.sentinel.S2_Band_Reader`` and its ``resample()`` method directly.

Copyright (C) 2022 Gregor Perich & Lukas Valentin Graf

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

import cv2
import rasterio as rio
import matplotlib.pyplot as plt

from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from eodal.config import get_settings
from eodal.config.sentinel2 import Sentinel2 as s2
from eodal.core.raster import RasterCollection
from eodal.core.sensors.sentinel2 import Sentinel2
from eodal.core.utils.sentinel2 import read_s2_tcifile
from eodal.core.utils.sentinel2 import read_s2_sclfile
from eodal.utils.constants.sentinel2 import s2_band_mapping
from eodal.utils.constants.sentinel2 import ProcessingLevels
from eodal.utils.sentinel2 import get_S2_processing_level

Settings = get_settings()
logger = Settings.logger
S2 = s2()


def _get_output_file_names(
    in_dir: Path, resampling_method: str, target_resolution: Union[int, float]
) -> Dict[str, str]:
    """
    auxiliary method to get the output file names
    for the band-stack, the quicklooks and (if applicable) the
    SCL.

    The file-naming convention for the band-stack and previews is
    ``
    <date>_<tile>_<processing_level>_<sensor>_<resampling_method>_<spatial_resolution>
    ``

    :param in_dir:
        path of the .SAFE directory where the S2 data resides.
    :param resampling_method:
        name of the resampling method used
    :param target_resolution:
        spatial resolution of the output
    :return:
        dict with output file names
    """
    # get S2 UID
    s2_uid = in_dir.name

    splitted = s2_uid.split("_")
    date = splitted[2].split("T")[0]
    tile = splitted[-2]
    level = splitted[1]
    sensor = splitted[0]
    resolution = f"{int(target_resolution)}m"

    # define filenames
    basename = (
        date
        + "_"
        + tile
        + "_"
        + level
        + "_"
        + sensor
        + "_"
        + resampling_method
        + "_"
        + resolution
    )

    return {
        "bandstack": f"{basename}.jp2",
        "rgb_preview": f"{basename}.png",
        "scl_preview": f"{basename}_SCL.png",
        "scl": f"{basename}_SCL.tiff",
    }


def _get_resampling_name(resampling_method: int) -> str:
    """
    auxiliary method to map opencv's integer codes to meaningful resampling names
    (unknown if the method is not known)

    :param resampling_method:
        integer code from opencv2 for one of its image resizing methods
    :return:
        resampling method name or 'unknown' if the integer code cannot be
        translated
    """
    translator = {
        0: "nearest",
        1: "linear",
        2: "cubic",
        3: "area",
        4: "lanczos",
        5: "linear-exact",
        6: "nearest-exact",
    }

    return translator.get(resampling_method, "unknown")


def create_rgb_preview(
    out_dir: Path, reader: RasterCollection, out_filename: str
) -> Path:
    """
    Creates the RGB quicklook image (stored in a sub-directory).

    :param out_dir:
        directory where the band-stacked geoTiff are written to
    :param s2_stack:
        opened Sat_Data_Reader with 'tci' band
    :param out_filename:
        file name of the resulting RGB quicklook image (*.png)
    """
    # RGB previews are stored in their own sub-directory
    rgb_subdir = out_dir.joinpath(Settings.SUBDIR_RGB_PREVIEWS)
    if not rgb_subdir.exists():
        rgb_subdir.mkdir()

    out_file = rgb_subdir.joinpath(out_filename)

    fig_rgb = reader.plot_multiple_bands(["red", "green", "blue"])
    fig_rgb.savefig(fname=out_file, bbox_inches="tight", dpi=150)
    plt.close(fig_rgb)

    return out_file


def create_scl_preview(out_dir: Path, reader: Sentinel2, out_filename: str) -> Path:
    """
    Creates the SCL quicklook image (stored in a sub-directory).

    :param out_dir:
        directory where the band-stacked geoTiff are written to
    :param s2_stack:
        opened S2_Band_Reader with 'scl' band
    :param out_filename:
        file name of the resulting SCL quicklook image (*.png)
    :return:
        path to output file
    """
    # SCL previews are stored in their own sub-directory alongside with the RGBs
    rgb_subdir = out_dir.joinpath(Settings.SUBDIR_RGB_PREVIEWS)
    if not rgb_subdir.exists():
        rgb_subdir.mkdir()

    out_file = rgb_subdir.joinpath(out_filename)

    fig_scl = reader.plot_scl()
    fig_scl.savefig(fname=out_file, bbox_inches="tight", dpi=150)
    plt.close(fig_scl)

    return out_file


def create_scl(out_dir: Path, reader: Sentinel2, out_filename: str) -> Path:
    """
    Creates the SCL raster datasets (stored in a sub-directory).

    :param out_dir:
        directory where the band-stacked geoTiff are written to
    :param reader:
        opened ``Sentinel2Handler`` with 'scl' band
    :param out_filename:
        file name of the resulting SCL raster image (*.tiff)
    :return:
        file-path of output dataset
    """
    scl_subdir = out_dir.joinpath(Settings.SUBDIR_SCL_FILES)
    if not scl_subdir.exists():
        scl_subdir.mkdir()

    out_file = scl_subdir.joinpath(out_filename)
    reader.to_rasterio(fpath_raster=out_file, band_selection=["SCL"])
    return out_file


TARGET_RESOLUTIONS: List[int] = [10, 20]


def resample_and_stack_s2(
    in_dir: Path,
    out_dir: Path,
    target_resolution: Optional[Union[int, float]] = 10,
    interpolation_method: Optional[int] = cv2.INTER_NEAREST_EXACT,
    skip_60m_bands: Optional[bool] = True,
) -> Dict[str, Union[Path, str, int, float]]:
    """
    Function to spatially resample a S2 scene in *.SAFE format and write it to a
    single, stacked geoTiff. Creates also a RGB preview png-file of the scene and
    stores the scene classification layer that comes with L2A products in 10m spatial
    resolution. Possible spatial resolution values are 10 and 20m. The 60m bands
    are not considered.

    The function checks the processing level of the data (L1C or L2A) based on the
    name of the .SAFE dataset.

    Depending on the processing level the output will look a bit differently:

    * in L1C level (top-of-atmosphere) the band-stack of the spectral bands and
      the RGB quicklook is produced
    * in L2A level (bottom-of-atmosphere) the same inputs as in the L1C case
      are generated PLUS the scene classification layer (SCL) resampled to 10m
      spatial resolution

    IMPORTANT: If only a small area of interest shall be processed, also consider
    ``eodal.core.sensors.sentinel2.Sat_Data_Reader.resample`` since this function works
    on the **full** scene extent, only.

    :param in_dir:
        path of the .SAFE directory where the S2 data resides.
    :param out_dir:
        path where to save the resampled & stacked geoTiff files to.
    :param target_resolution:
        target spatial resolution you want to resample to. Must be one of
        [10, 20]. The default is 10 (meters).
    :param interpolation_method:
        The interpolation algorithm you want to use for spatial resampling.
        The default is opencv's ``cv2.INTER_NEAREST_EXACT``. See the opencv documentation
        for other options such as ``cv2.INTER_LINEAR``.
    :param skip_60m_bands:
        if False (default) does not resample the 60m bands. If True, also includes the
        60m bands (B01, B09). B10 is never processed.
    :returns:
        dictionary with filepaths to bandstack, rgb_quicklook, and (L2A, only) SCL
        and related metadata
    """
    # check passed spatial resolution
    if target_resolution not in TARGET_RESOLUTIONS:
        raise ValueError(f"Spatial resolution must be one out of {TARGET_RESOLUTIONS}")

    # determine name of the resampling method
    resampling_method_str = _get_resampling_name(resampling_method=interpolation_method)

    # get output filenames
    out_file_names = _get_output_file_names(
        in_dir=in_dir,
        resampling_method=resampling_method_str,
        target_resolution=target_resolution,
    )
    # save resampling method and spatial resolution
    out_file_names["resampling_method"] = resampling_method_str
    out_file_names["spatial_resolution"] = target_resolution

    # get the TCI quicklook image first
    try:
        tci = read_s2_tcifile(in_dir)
    except Exception as e:
        logger.error(f"Could not read TCI file from {in_dir}: {e}")
        return {}
    # save to file in RGB sub-directory
    try:
        out_file_rgb_preview = create_rgb_preview(
            out_dir=out_dir, reader=tci, out_filename=out_file_names["rgb_preview"]
        )
        out_file_names.update({"rgb_preview": out_file_rgb_preview})
    except Exception as e:
        logger.error(f"Generation of RGB preview from {in_dir} failed: {e}")
        return {}
    logger.info(f"Generated RGB preview image from {in_dir}")

    # its meta information serves a blue-print for writing the output
    meta = tci["blue"].meta
    tci = None

    # get scene classification layer if available (L2A processing level)
    processing_level = get_S2_processing_level(dot_safe_name=in_dir)
    if processing_level == ProcessingLevels.L2A:
        try:
            scl = read_s2_sclfile(in_dir)
        except Exception as e:
            logger.error(f"Could not read SCL file from {in_dir}: {e}")
            return {}
        # save as preview image and geoTiff dataset after resampling to 10m
        out_file_scl_preview = create_scl_preview(
            out_dir=out_dir, reader=scl, out_filename=out_file_names["scl_preview"]
        )
        out_file_names.update({"scl_preview": out_file_scl_preview})
        # resample to 10m spatial resolution and save to geoTiff
        # we always use pixel division for the SCL file
        try:
            scl.resample(target_resolution=target_resolution, inplace=True)
        except Exception as e:
            logger.error(f"Resampling of SCL file from {in_dir} failed: {e}")
            return {}
        logger.info(f"Generated SCL preview image from {in_dir}")
        try:
            out_file_scl = create_scl(
                out_dir=out_dir, reader=scl, out_filename=out_file_names["scl"]
            )
            out_file_names.update({"scl": out_file_scl})
        except Exception as e:
            logger.error(f"Generation of SCL file from {in_dir} failed: {e}")
            return {}
        logger.info(f"Generated SCL geoTiff (10m) from {in_dir}")
    # if scl is not available set it to empty string in the dictionary of filenames
    else:
        out_file_names["scl"] = ""
        out_file_names["scl_preview"] = ""

    # get driver for output file
    fname_bandstack = out_dir.joinpath(out_file_names["bandstack"])
    out_file_names.update({"bandstack": fname_bandstack})
    driver = rio.drivers.driver_from_extension(fname_bandstack)

    # check if the resolution fits
    if abs(meta["transform"][0]) != target_resolution:
        if processing_level == ProcessingLevels.L2A:
            # take meta from SCL layer since this layer has been resampled, already
            meta = scl["SCL"].meta
        else:
            raise NotImplementedError(
                "Uups - we need to implement this functionality first!"
            )

    # update meta dictionary
    meta.update(
        {
            "count": 10,  # Sentinel-2 has 10 bands relevant for agriculture
            "dtype": "uint16",  # Sentinel-2 data is stored as unsigned integers (16bit)
            "driver": driver,
            "REVERSIBLE": "YES",
            "QUALITY": 100,
        }
    )
    # open output dataset
    s2_bands = list(s2_band_mapping.keys())
    # SCL is a separate file (see above)
    s2_bands.remove("SCL")
    # 60m bands ignored if selected
    if skip_60m_bands:
        if "B01" in s2_bands:
            s2_bands.remove("B01")
        if "B09" in s2_bands:
            s2_bands.remove("B09")

    # write bands to the output dataset iteratively
    with rio.open(fname_bandstack, "w+", **meta) as dst:

        logger.info(f"Opening output dataset {fname_bandstack}")
        # loop over S2 bands: read from .SAFE, resample if required and write to output
        for idx, s2_band in enumerate(s2_bands):
            try:
                src = Sentinel2().from_safe(
                    in_dir=in_dir,
                    band_selection=[s2_band],
                    read_scl=False,
                    apply_scaling=False,
                )
            except Exception as e:
                logger.error(f"Could not read band {s2_band} from {in_dir}: {e}")
                return {}
            # get color name of the band (used in reader)
            band_alias = s2_band_mapping[s2_band]
            # check resolution of the band
            band_res = abs(src[s2_band].geo_info.pixres_x)
            # resample band if required
            if band_res != target_resolution:
                try:
                    src.resample(
                        target_resolution=target_resolution,
                        interpolation_method=interpolation_method,
                        band_selection=[s2_band],
                        inplace=True,
                    )
                except Exception as e:
                    logger.error(
                        f"Resampling of band {s2_band}/{band_alias} "
                        f"({idx+1}/{len(s2_bands)} failed: {e}"
                    )
                    return {}

                logger.info(
                    f'Resampled band {s2_band} - "{band_alias.upper()}" '
                    f"({idx+1}/{len(s2_bands)}) to {int(target_resolution)}m "
                    f"from {in_dir}"
                )
            # write band to dst
            dst.set_band_description(idx + 1, s2_band)
            dst.write(src[s2_band].values, idx + 1)
            logger.info(
                f'Wrote band {s2_band} - "{band_alias.upper()}" ({idx+1}/{len(s2_bands)}) '
                f"from {in_dir} into {fname_bandstack}"
            )
            src = None
        logger.info(f"Finished writing bands to {fname_bandstack}")

    return out_file_names
