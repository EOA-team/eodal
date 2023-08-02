"""
Utility functions for working with timestamps.
"""

from datetime import datetime, date


def datetime_to_date(
        timestamp: str,
) -> date:
    """
    Convert `timestamp` received from STAC to `date` objects.

    :param timestamp:
        Timestamp received from STAC (e.g., '2023-05-16T10:15:46.380697Z').
    :return:
        Date object (e.g., 2023-05-16).
    """
    return datetime.strptime(
        timestamp.split("T")[0], "%Y-%m-%d"
    ).date()
