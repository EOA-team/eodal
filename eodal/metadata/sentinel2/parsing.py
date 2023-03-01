#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module contains functions to extract relevant scene-specific
Sentinel-2 metadata supporting L1C and L2A (sen2core-derived) processing levels

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
import time
import numpy as np
from datetime import datetime
from xml.dom import minidom
from pyproj import Transformer
from pathlib import Path
import pandas as pd
from typing import Any, Dict, Optional, Tuple
from datetime import date

from eodal.config import get_settings
from eodal.utils.constants.sentinel2 import s2_band_mapping
from eodal.utils.exceptions import UnknownProcessingLevel
from eodal.utils.exceptions import InputError
from eodal.utils.warnings import NothingToDo

logger = get_settings().logger


def parse_MTD_DS(in_file: Path) -> Dict[str, Any]:
    """
    Parses the MTD_DS.xml located in tghe /DATASTRIP folder
    in each .SAFE dataset. The xml contains the noise model parameters
    alpha and beta as well as physical gain factors
    required to calculate the radiometric uncertainty
    of the Level-1C data. The extraction of this data is therefore
    optional.

    :param in_file:
        filepath of the scene metadata xml (MTD_DS.xml)
    :return metadata:
        dictionary with extracted noise model parameters, alpha
        and beta, per spectral band of MSI
    """
    # parse the xml file into a minidom object
    xmldoc = minidom.parse(str(in_file))

    # now, the values of some relevant tags can be extracted:
    metadata = dict()
    band_names = list(s2_band_mapping.keys())

    datatakeIdentifier_xml = xmldoc.getElementsByTagName("Datatake_Info")
    element = datatakeIdentifier_xml[0]
    datatakeIdentifier = element.getAttribute("datatakeIdentifier")
    metadata["datatakeidentifier"] = datatakeIdentifier

    # extract noise model parameters alpha and beta for all bands
    alpha_values = xmldoc.getElementsByTagName("ALPHA")
    beta_values = xmldoc.getElementsByTagName("BETA")
    # loop over bands and store values of alpha and beta
    for idx, elem in enumerate(zip(alpha_values, beta_values)):
        alpha = float(elem[0].firstChild.nodeValue)
        beta = float(elem[1].firstChild.nodeValue)
        metadata[f"alpha_{band_names[idx]}"] = alpha
        metadata[f"beta_{band_names[idx]}"] = beta

    # extract physical gans of the single spectral bands
    physical_gains = xmldoc.getElementsByTagName("PHYSICAL_GAINS")
    for idx, elem in enumerate(physical_gains):
        physical_gain = float(elem.firstChild.nodeValue)
        metadata[f"physical_gain_{band_names[idx]}"] = physical_gain

    return metadata


def parse_MTD_TL(in_file: Path) -> Dict[str, Any]:
    """
    Parses the MTD_TL.xml metadata file provided by ESA.This metadata
    XML is usually placed in the GRANULE subfolder of a ESA-derived
    S2 product and named 'MTD_TL.xml'.

    The 'MTD_TL.xml' is available for both processing levels (i.e.,
    L1C and L2A). The function is able to handle both processing
    sources and returns some entries available in L2A processing level,
    only, as None type objects.

    The function extracts the most important metadata from the XML and
    returns a dict with those extracted entries.

    :param in_file:
        filepath of the scene metadata xml 8MTD_TL.xml)
    :return metadata:
        dict with extracted metadata entries
    """
    # parse the xml file into a minidom object
    xmldoc = minidom.parse(in_file)

    # now, the values of some relevant tags can be extracted:
    metadata = dict()

    # get tile ID of L2A product and its corresponding L1C counterpart
    tile_id_xml = xmldoc.getElementsByTagName("TILE_ID")
    # adaption to older Sen2Cor version
    check_l1c = True
    if len(tile_id_xml) == 0:
        tile_id_xml = xmldoc.getElementsByTagName("TILE_ID_2A")
        check_l1c = False
    tile_id = tile_id_xml[0].firstChild.nodeValue
    scene_id = tile_id.split(".")[0]
    metadata["SCENE_ID"] = scene_id

    # check if the scene is L1C or L2A
    is_l1c = False
    if check_l1c:
        try:
            l1c_tile_id_xml = xmldoc.getElementsByTagName("L1C_TILE_ID")
            l1c_tile_id = l1c_tile_id_xml[0].firstChild.nodeValue
            l1c_tile_id = l1c_tile_id.split(".")[0]
            metadata["L1C_TILE_ID"] = l1c_tile_id
        except Exception:
            logger.info(f"{scene_id} is L1C processing level")
            is_l1c = True

    # sensing time (acquisition time)
    sensing_time_xml = xmldoc.getElementsByTagName("SENSING_TIME")
    sensing_time = sensing_time_xml[0].firstChild.nodeValue
    metadata["SENSING_TIME"] = sensing_time
    metadata["SENSING_DATE"] = datetime.strptime(
        sensing_time.split("T")[0], "%Y-%m-%d"
    ).date()

    # number of rows and columns for each resolution -> 10, 20, 60 meters
    nrows_xml = xmldoc.getElementsByTagName("NROWS")
    ncols_xml = xmldoc.getElementsByTagName("NCOLS")
    resolutions = ["_10m", "_20m", "_60m"]
    # order: 10, 20, 60 meters spatial resolution
    for ii in range(3):
        nrows = nrows_xml[ii].firstChild.nodeValue
        ncols = ncols_xml[ii].firstChild.nodeValue
        metadata["NROWS" + resolutions[ii]] = int(nrows)
        metadata["NCOLS" + resolutions[ii]] = int(ncols)

    # EPSG-code
    epsg_xml = xmldoc.getElementsByTagName("HORIZONTAL_CS_CODE")
    epsg = epsg_xml[0].firstChild.nodeValue
    metadata["EPSG"] = int(epsg.split(":")[1])

    # Upper Left Corner coordinates -> is the same for all three resolutions
    ulx_xml = xmldoc.getElementsByTagName("ULX")
    uly_xml = xmldoc.getElementsByTagName("ULY")
    ulx = ulx_xml[0].firstChild.nodeValue
    uly = uly_xml[0].firstChild.nodeValue
    metadata["ULX"] = float(ulx)
    metadata["ULY"] = float(uly)
    # endfor

    # extract the mean zenith and azimuth angles
    # the sun angles come first followed by the mean angles per band
    zenith_angles = xmldoc.getElementsByTagName("ZENITH_ANGLE")
    metadata["SUN_ZENITH_ANGLE"] = float(zenith_angles[0].firstChild.nodeValue)

    azimuth_angles = xmldoc.getElementsByTagName("AZIMUTH_ANGLE")
    metadata["SUN_AZIMUTH_ANGLE"] = float(azimuth_angles[0].firstChild.nodeValue)

    # get the mean zenith and azimuth angle over all bands
    sensor_zenith_angles = [float(x.firstChild.nodeValue) for x in zenith_angles[1::]]
    metadata["SENSOR_ZENITH_ANGLE"] = np.mean(np.asarray(sensor_zenith_angles))

    sensor_azimuth_angles = [float(x.firstChild.nodeValue) for x in azimuth_angles[1::]]
    metadata["SENSOR_AZIMUTH_ANGLE"] = np.mean(np.asarray(sensor_azimuth_angles))

    # extract scene relevant data about nodata values, cloud coverage, etc.
    cloudy_xml = xmldoc.getElementsByTagName("CLOUDY_PIXEL_PERCENTAGE")
    cloudy = cloudy_xml[0].firstChild.nodeValue
    metadata["CLOUDY_PIXEL_PERCENTAGE"] = float(cloudy)

    degraded_xml = xmldoc.getElementsByTagName("DEGRADED_MSI_DATA_PERCENTAGE")
    degraded = degraded_xml[0].firstChild.nodeValue
    metadata["DEGRADED_MSI_DATA_PERCENTAGE"] = float(degraded)

    # the other tags are available in L2A processing level, only
    if not is_l1c:
        nodata_xml = xmldoc.getElementsByTagName("NODATA_PIXEL_PERCENTAGE")
        nodata = nodata_xml[0].firstChild.nodeValue
        metadata["NODATA_PIXEL_PERCENTAGE"] = float(nodata)

        darkfeatures_xml = xmldoc.getElementsByTagName("DARK_FEATURES_PERCENTAGE")
        darkfeatures = darkfeatures_xml[0].firstChild.nodeValue
        metadata["DARK_FEATURES_PERCENTAGE"] = float(darkfeatures)

        cs_xml = xmldoc.getElementsByTagName("CLOUD_SHADOW_PERCENTAGE")
        cs = cs_xml[0].firstChild.nodeValue
        metadata["CLOUD_SHADOW_PERCENTAGE"] = float(cs)

        veg_xml = xmldoc.getElementsByTagName("VEGETATION_PERCENTAGE")
        veg = veg_xml[0].firstChild.nodeValue
        metadata["VEGETATION_PERCENTAGE"] = float(veg)

        noveg_xml = xmldoc.getElementsByTagName("NOT_VEGETATED_PERCENTAGE")
        noveg = noveg_xml[0].firstChild.nodeValue
        metadata["NOT_VEGETATED_PERCENTAGE"] = float(noveg)

        water_xml = xmldoc.getElementsByTagName("WATER_PERCENTAGE")
        water = water_xml[0].firstChild.nodeValue
        metadata["WATER_PERCENTAGE"] = float(water)

        unclass_xml = xmldoc.getElementsByTagName("UNCLASSIFIED_PERCENTAGE")
        unclass = unclass_xml[0].firstChild.nodeValue
        metadata["UNCLASSIFIED_PERCENTAGE"] = float(unclass)

        cproba_xml = xmldoc.getElementsByTagName("MEDIUM_PROBA_CLOUDS_PERCENTAGE")
        cproba = cproba_xml[0].firstChild.nodeValue
        metadata["MEDIUM_PROBA_CLOUDS_PERCENTAGE"] = float(cproba)

        hcproba_xml = xmldoc.getElementsByTagName("HIGH_PROBA_CLOUDS_PERCENTAGE")
        hcproba = hcproba_xml[0].firstChild.nodeValue
        metadata["HIGH_PROBA_CLOUDS_PERCENTAGE"] = float(hcproba)

        thcirrus_xml = xmldoc.getElementsByTagName("THIN_CIRRUS_PERCENTAGE")
        thcirrus = thcirrus_xml[0].firstChild.nodeValue
        metadata["THIN_CIRRUS_PERCENTAGE"] = float(thcirrus)

        snowice_xml = xmldoc.getElementsByTagName("SNOW_ICE_PERCENTAGE")
        snowice = snowice_xml[0].firstChild.nodeValue
        metadata["SNOW_ICE_PERCENTAGE"] = float(snowice)

    # calculate the scene footprint in geographic coordinates
    metadata["geom"] = get_scene_footprint(sensor_data=metadata)

    return metadata


def parse_MTD_MSI(in_file: str) -> Dict[str, Any]:
    """
    parses the MTD_MSIL1C or MTD_MSIL2A metadata file that is delivered with
    ESA Sentinel-2 L1C and L2A products, respectively.

    The file is usually placed directly in the .SAFE root folder of an
    unzipped Sentinel-2 L1C or L2A scene.

    The extracted metadata is returned as a dict.

    :param in_file:
        filepath of the scene metadata xml (MTD_MSI2A.xml or MTD_MSIL1C.xml)
    """
    # parse the xml file into a minidom object
    xmldoc = minidom.parse(in_file)

    # check the version of the xml. Unfortunately, different sen2cor version
    # also produced slightly different metadata xmls
    if xmldoc.getElementsByTagName("L2A_Product_Info"):
        tag_list = ["PRODUCT_URI_2A"]
    else:
        tag_list = ["PRODUCT_URI"]

    # datatake identifier
    datatakeIdentifier_xml = xmldoc.getElementsByTagName("Datatake")
    element = datatakeIdentifier_xml[0]
    datatakeIdentifier = element.getAttribute("datatakeIdentifier")

    # define further tags to extract
    tag_list.extend(
        [
            "PROCESSING_LEVEL",
            "SENSING_ORBIT_NUMBER",
            "SPACECRAFT_NAME",
            "SENSING_ORBIT_DIRECTION",
        ]
    )

    metadata = dict.fromkeys(tag_list)

    for tag in tag_list:
        xml_elem = xmldoc.getElementsByTagName(tag)
        if tag == "PRODUCT_URI_2A":
            metadata["PRODUCT_URI"] = xml_elem[0].firstChild.data
            metadata.pop("PRODUCT_URI_2A")
        else:
            metadata[tag] = xml_elem[0].firstChild.data

    metadata["datatakeIdentifier"] = datatakeIdentifier

    # extract PDGS baseline
    metadata["pdgs_baseline"] = metadata["PRODUCT_URI"].split("_")[3]

    # stupid Sen2Cor is not consistent here ...
    if metadata["PROCESSING_LEVEL"] == "Level-2Ap":
        metadata["PROCESSING_LEVEL"] = "Level-2A"

    # reflectance conversion factor (U)
    reflectance_conversion_xml = xmldoc.getElementsByTagName("U")
    reflectance_conversion = float(reflectance_conversion_xml[0].firstChild.nodeValue)
    metadata["reflectance_conversion"] = reflectance_conversion

    # extract solar irradiance for the single bands
    bands = [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B8A",
        "B09",
        "B10",
        "B11",
        "B12",
    ]
    sol_irrad_xml = xmldoc.getElementsByTagName("SOLAR_IRRADIANCE")
    for idx, band in enumerate(bands):
        metadata[f"SOLAR_IRRADIANCE_{band}"] = float(
            sol_irrad_xml[idx].firstChild.nodeValue
        )

    # S2 tile
    metadata["TILE_ID"] = metadata["PRODUCT_URI"].split("_")[5]

    return metadata


def get_scene_footprint(sensor_data: dict) -> str:
    """
    get the footprint (geometry) of a scene by calculating its
    extent using the original UTM coordinates of the scene.
    The obtained footprint is then converted to WGS84 geographic
    coordinates and returned as Extended Well-Known-Text (EWKT)
    string.

    :param sensor_data:
        dict with ULX, ULY, NROWS_10m, NCOLS_10m, EPSG entries
        obtained from the MTD_TL.xml file
    :return wkt:
        extended well-known-text representation of the scene
        footprint
    """
    dst_crs = "epsg:4326"
    # get the EPSG-code
    epsg = sensor_data["EPSG"]
    src_crs = f"epsg:{epsg}"
    # the pixelsize is set to 10 m
    pixelsize = 10.0

    # use per default the 10m-representation
    ulx = sensor_data["ULX"]  # upper left x
    uly = sensor_data["ULY"]  # upper left y
    nrows = sensor_data["NROWS_10m"]  # number of rows
    ncols = sensor_data["NCOLS_10m"]  # number of columns

    # calculate the other image corners (upper right, lower left, lower right)
    urx = ulx + (ncols - 1) * pixelsize  # upper right x
    ury = uly  # upper right y
    llx = ulx  # lower left x
    lly = uly - (nrows + 1) * pixelsize  # lower left y
    lrx = urx  # lower right x
    lry = lly  # lower right y

    # transform coordinates to WGS84
    transformer = Transformer.from_crs(src_crs, dst_crs)
    uly, ulx = transformer.transform(xx=ulx, yy=uly)
    ury, urx = transformer.transform(xx=urx, yy=ury)
    lly, llx = transformer.transform(xx=llx, yy=lly)
    lry, lrx = transformer.transform(xx=lrx, yy=lry)

    wkt = f"SRID=4326;"
    wkt += f"POLYGON(({ulx} {uly},{urx} {ury},{lrx} {lry},{llx} {lly},{ulx} {uly}))"

    return wkt


def parse_s2_scene_metadata(
    in_dir: Path, extract_datastrip: Optional[bool] = False
) -> Tuple[Dict[str, Any]]:
    """
    wrapper function to extract metadata from ESA Sentinel-2
    mapper. It returns a dict with the metadata most important
    to characterize a given Sentinel-2 scene (mtd_msi).
    Optionally, some information about the datastrip can be
    extracted as well (MTD_DS.xml); this information is required
    for the uncertainty modelling and therefore not extracted by
    default.

    The function works on both, L1C and L2A (sen2cor-based)
    processing levels. The amount of metadata, however, is
    reduced in the case of L1C since no scene classification
    information is available.

    NOTE: In order to identify mapper and their processing level
    correctly, L2A mapper must have '_MSIL2A_' occuring somewhere
    in the filepath. For L1C, it must be '_MSIL1C_'.

    :param in_dir:
        directory containing the L1C or L2A Sentinel-2 scene
    :param extract_datastrip:
        If True reads also metadata from the datastrip xml file
        (MTD_DS.xml)
    :return mtd_msi:
        dict with extracted metadata items
    """

    # depending on the processing level (supported: L1C and
    # L2A) metadata has to be extracted slightly differently
    # because of different file names and storage locations
    if str(in_dir).find("_MSIL2A_") > 0:
        # scene is L2A
        mtd_msil2a_xml = str(next(Path(in_dir).rglob("MTD_MSIL2A.xml")))
        mtd_msi = parse_MTD_MSI(in_file=mtd_msil2a_xml)
        with open(mtd_msil2a_xml, "r") as xml_file:
            mtd_msi["mtd_msi_xml"] = xml_file.read().strip()

    elif str(in_dir).find("_MSIL1C_") > 0:
        # scene is L1C
        mtd_msil1c_xml = str(next(Path(in_dir).rglob("MTD_MSIL1C.xml")))
        mtd_msi = parse_MTD_MSI(in_file=mtd_msil1c_xml)
        with open(mtd_msil1c_xml, "r") as xml_file:
            mtd_msi["mtd_msi_xml"] = xml_file.read().strip()

    else:
        raise UnknownProcessingLevel(f"{in_dir} seems not be a valid Sentinel-2 scene")

    mtd_tl_xml = str(next(Path(in_dir).rglob("MTD_TL.xml")))
    with open(mtd_tl_xml) as xml_file:
        mtd_msi["mtd_tl_xml"] = xml_file.read().strip()

    # datastrip xml (optional)
    mtd_ds = {}
    if extract_datastrip:
        mtd_ds_xml = str(next(Path(in_dir).rglob("MTD_DS.xml")))
        mtd_ds = parse_MTD_DS(in_file=mtd_ds_xml)

    mtd_msi.update(parse_MTD_TL(in_file=mtd_tl_xml))

    # storage location and path handling
    storage_path = in_dir.parent.as_posix()
    mtd_msi["storage_share"] = storage_path
    mtd_msi["path_type"] = "Posix"
    mtd_msi["storage_device_ip"] = ""

    return mtd_msi, mtd_ds


def loop_s2_archive(
    in_dir: Path,
    extract_datastrip: Optional[bool] = False,
    get_newest_datasets: Optional[bool] = False,
    last_execution_date: Optional[date] = None,
) -> Tuple[pd.DataFrame]:
    """
    wrapper function to loop over an entire archive (i.e., collection) of
    Sentinel-2 mapper in either L1C or L2A processing level or a mixture
    thereof.

    The function returns a pandas dataframe for all found entries in the
    archive (i.e., directory). Each row in the dataframe denotes one scene.

    :param in_dir:
        directory containing the Sentinel-2 data (L1C and/or L2A
        processing level). Sentinel-2 mapper are assumed to follow ESA's
        .SAFE naming convention and structure
    :param extract_datastrip:
        If True reads also metadata from the datastrip xml file
        (MTD_DS.xml)
    :param get_newest_datasets:
        if set to True only datasets newer than a user-defined time stamp
        will be considered for ingestion into the database. This is particularly
        useful for updating the database after new mapper have been downloaded
        or processed.
    :param last_execution_date:
        if get_newest_datasets is True this variable needs to be set. All
        datasets younger than that date will be considered for ingestion
        into the database.
    :return:
        dataframe with metadata of all mapper handled by the function
        call
    """

    # check inputs if only latest datasets shall be considered
    if get_newest_datasets:
        if last_execution_date is None:
            raise InputError(
                "A timestamp must be provided when the only newest datasets shall be considered"
            )

    # search for .SAFE subdirectories identifying the single mapper
    # some data providers, however, do not name their products following the
    # ESA convention (.SAFE is missing)
    s2_scenes = glob.glob(str(in_dir.joinpath("*.SAFE")))
    n_scenes = len(s2_scenes)

    if n_scenes == 0:
        s2_scenes = [f for f in in_dir.iterdir() if f.is_dir()]
        n_scenes = len(s2_scenes)
        if n_scenes == 0:
            raise UnknownProcessingLevel("No Sentinel-2 mapper were found")

    # if only mapper after a specific timestamp shall be considered drop
    # those from the list which are "too old"
    if get_newest_datasets:
        filtered_scenes = []
        # convert date to Unix timestamp
        last_execution = time.mktime(last_execution_date.timetuple())
        for s2_scene in s2_scenes:
            s2_scene_path = Path(s2_scene)
            if s2_scene_path.stat().st_ctime >= last_execution:
                filtered_scenes.append(s2_scene)
        s2_scenes = filtered_scenes
        if len(s2_scenes) == 0:
            raise NothingToDo(
                f'No mapper younger than {datetime.strftime(last_execution_date, "%Y-%m-%d")} found'
            )

    # loop over the mapper
    metadata_scenes = []
    ql_ds_scenes = []
    error_file = open(in_dir.joinpath("errored_datasets.txt"), "w+")
    for idx, s2_scene in enumerate(s2_scenes):
        logger.info(
            f"Extracting metadata of {os.path.basename(s2_scene)} ({idx+1}/{n_scenes})"
        )
        try:
            mtd_scene, mtd_ds_scene = parse_s2_scene_metadata(
                in_dir=Path(s2_scene), extract_datastrip=extract_datastrip
            )
        except Exception as e:
            error_file.write(Path(s2_scene).name)
            error_file.flush()
            logger.error(f"Extraction of metadata failed {s2_scene}: {e}")
            continue
        metadata_scenes.append(mtd_scene)
        ql_ds_scenes.append(mtd_ds_scene)

    # convert to pandas dataframe and return
    return (
        pd.DataFrame.from_dict(metadata_scenes),
        pd.DataFrame.from_dict(ql_ds_scenes),
    )
