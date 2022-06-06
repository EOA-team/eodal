"""
Sentinel-2 records data in so-called datatakes. When a datatake is over and a new
begins the acquired image data is written to different files (based on the datatake
time). Sometimes, this cause scenes of a single acquisition date to be split into
two datasets which differ in their datatake. Thus, both datasets have a reasonable
amount of blackfill in those areas not covered by the datatake they belong to. For
users of satellite data, however, it is much more convenient to have those split
scenes merged into one since the division into two scenes by the datatake has
technical reasons only.

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

import shutil
import rasterio as rio

from pathlib import Path
from typing import Dict

from eodal.config import get_settings
from eodal.core.sensors import Sentinel2
from eodal.core.raster import RasterCollection
from eodal.operational.mapping.merging import merge_datasets
from eodal.operational.resampling.sentinel2.resample_and_stack import (
    resample_and_stack_s2,
)
from eodal.operational.resampling.sentinel2.resample_and_stack import create_rgb_preview
from eodal.operational.resampling.sentinel2.resample_and_stack import create_scl_preview
from eodal.utils.constants.sentinel2 import s2_band_mapping

Settings = get_settings()
logger = Settings.logger


def merge_split_scenes(
    scene_1: Path, scene_2: Path, out_dir: Path, **kwargs
) -> Dict[str, Path]:
    """
    merges two Sentinel-2 datasets in .SAFE formatof the same sensing date and tile
    split by the datatake beginning/ end.

    First, both scenes are resampled to 10m and stacked in a temporary working directory;
    second, they are merged together so that the blackfill of the first scenes is replaced
    by the values of the second one.
    SCL (if available) and previews are managed accordingly.

    :param scene_1:
        .SAFE directory containing the first of two scenes split by the datatake beginning/
        end of Sentinel-2
    :param scene_2:
        .SAFE directory containing the first of two scenes split by the datatake beginning/
        end of Sentinel-2
    :param out_dir:
        directory where to save the final outputs to. In this directory a temporary
        working directory for storing intermediate products is generated.
    :param kwargs:
        key word arguments to pass to resample_and_stack_S2.
    :return:
        dictionary with filepaths to bandstack, rgb_quicklook, and (L2A, only) SCL
    """

    # check if working directory exists
    working_dir = out_dir.joinpath("temp_blackfill")
    if not working_dir.exists():
        working_dir.mkdir()

    # save the outputs of the two scenes to different sub-directories within the working
    # directory to avoid to override the output
    out_dirs = [working_dir.joinpath("1"), working_dir.joinpath("2")]
    for _out_dir in out_dirs:
        if _out_dir.exists():
            # for clean start of next loop iteration
            shutil.rmtree(_out_dir)
        _out_dir.mkdir()

    # do the spatial resampling for the two scenes
    # first scene
    try:
        scene_out_1 = resample_and_stack_s2(
            in_dir=scene_1, out_dir=out_dirs[0], **kwargs
        )
    except Exception as e:
        logger.error(f"Resampling of {scene_1} failed: {e}")
        return {}

    # second scene
    try:
        scene_out_2 = resample_and_stack_s2(
            in_dir=scene_2, out_dir=out_dirs[1], **kwargs
        )
    except Exception as e:
        logger.error(f"Resampling of {scene_1} failed: {e}")
        return {}

    # merge band stacks
    # merged file has some name as the first scene and is directly written to target directory
    out_file = out_dir.joinpath(scene_out_1["bandstack"].name)
    # we create a temporary file first
    out_file_temp = working_dir.joinpath(out_file.name.split(".")[0] + "_temp.jp2")
    datasets = [scene_out_1["bandstack"], scene_out_2["bandstack"]]

    logger.info(f"Starting merging files {datasets[0]} and {datasets[1]}")

    # merge reflectance data
    try:
        merge_datasets(datasets=datasets, out_file=out_file_temp)
    except Exception as e:
        logger.error(f"Merging of {datasets[0]} and {datasets[1]} failed: {e}")
        return {}

    out_band_names = list(s2_band_mapping.keys())
    out_band_names.remove("SCL")
    if kwargs.get("skip_60m_bands", True):
        out_band_names.remove("B01")
        out_band_names.remove("B09")

    # set correct band descriptions and write final image to target directory
    meta = rio.open(out_file_temp, "r").meta
    meta.update({"QUALITY": "100", "REVERSIBLE": "YES"})

    with rio.open(out_file, "w", **meta) as dst:

        # open target file and write band by band + setting band names
        with rio.open(out_file_temp, "r") as src:
            for idx in range(meta["count"]):
                dst.set_band_description(idx + 1, out_band_names[idx])
                band_data = src.read(idx + 1)
                dst.write(band_data, idx + 1)

    logger.info(f"Merged datasets into {out_file}")

    # generate RGB preview image from merged dataset (and SCL if applicable)
    vis_bands = ["B02", "B03", "B04"]
    handler = RasterCollection.from_multi_band_raster(
        fpath_raster=out_file,
        band_names_src=vis_bands,
        band_names_dst=["blue", "green", "red"],
    )
    fname_rgb_preview = create_rgb_preview(
        out_dir=out_dir, reader=handler, out_filename=scene_out_1["rgb_preview"].name
    )
    handler = None

    fnames_out = {
        "bandstack": out_file,
        "rgb_preview": fname_rgb_preview,
        "scl": "",
        "scl_preview": "",
    }

    # check if SCL must be merged as well (L2A)
    if "scl" in scene_out_1.keys():

        scl_datasets = [scene_out_1["scl"], scene_out_2["scl"]]
        scl_out_dir = out_dir.joinpath(Path(Settings.SUBDIR_SCL_FILES))

        # create SCL directory if not yet there
        if not scl_out_dir.exists():
            scl_out_dir.mkdir()

        out_file_scl = scl_out_dir.joinpath(scene_out_1["scl"].name)

        try:
            merge_datasets(datasets=scl_datasets, out_file=out_file_scl)
        except Exception as e:
            logger.error(
                f"Could not merge {scl_datasets[0]} and {scl_datasets[1]}: {e}"
            )
            return fnames_out

        logger.info(f"Merged SCL files into {out_file_scl}")
        fnames_out["scl"] = out_file_scl

        # finally plot the scl file
        try:
            handler = Sentinel2().from_multi_band_raster(
                fpath_raster=out_file_scl, band_idx=1, band_names_dst=["SCL"]
            )

            fname_scl_preview = fname_rgb_preview.parent.joinpath(
                scene_out_1["scl_preview"].name
            )
            create_scl_preview(
                out_dir=out_dir, reader=handler, out_filename=fname_scl_preview
            )
            handler = None
        except Exception as e:
            logger.error(f"Could not generate SCL preview from {out_file}: {e}")
            return fnames_out

        fnames_out["scl_preview"] = fname_scl_preview

    # remove working directory
    try:
        shutil.rmtree(working_dir)
    except Exception as e:
        logger.error(f"Could not remove working directory {working_dir}: {e}")

    return fnames_out


if __name__ == "__main__":

    sat_dir = Path(
        "/home/graflu/public/Evaluation/Satellite_data/Sentinel-2/Rawdata/L2A/CH/2018"
    )

    scene_1 = sat_dir.joinpath(
        "S2A_MSIL2A_20180518T104021_N0207_R008_T32TLT_20180518T124554"
    )
    scene_2 = sat_dir.joinpath(
        "S2A_MSIL2A_20180518T104021_N0207_R008_T32TLT_20180518T125548"
    )

    out_dir = Path("/mnt/ides/Lukas/debug/Processed")

    fnames_out = merge_split_scenes(scene_1, scene_2, out_dir)
