"""
Constants for Planet Scope
"""

super_dove_band_mapping = {
    "B01": "coastal_blue",
    "B02": "blue",
    "B03": "green_i",
    "B04": "green",
    "B05": "yellow",
    "B06": "red",
    "B07": "rededge",
    "B08": "nir",
}

# sSperDove data is stored as uint16, to convert to 0-1 reflectance factors
# apply this gain factor
super_dove_gain_factor = 0.0001
