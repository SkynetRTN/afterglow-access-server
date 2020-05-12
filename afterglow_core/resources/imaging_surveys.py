#TODO remove unused imports
"""
Afterglow Core: access to the various imaging surveys via SkyView
(skyview.gsfc.nasa.gov)
"""

from __future__ import absolute_import, division, print_function

from astropy import units as u
from astropy.coordinates import Angle
from astroquery.skyview import SkyView
from flask import Response, request
from io import BytesIO

from skylib.io.conversion import get_image

from .. import app, json_response
from ..auth import auth_required
from ..errors import MissingFieldError, NotAcceptedError, ValidationError
from ..errors.imaging_survey import (
    UnknownSurveyError, SkyViewQueryError, NoSurveyDataError)


__all__ = ['default_size', 'survey_scales']


# Default pixel scale for each known survey (arcsec/pixel); needed to return
# an image of the given angular size without resampling, i.e. with pixel
# dimensions depending on the FOV
survey_scales = {
    '0035MHz': 360.0, '0408MHz': 1265.625, '1420MHz (Bonn)': 900.0,
    '2MASS-H': 1.0, '2MASS-J': 1.0, '2MASS-K': 1.0,
    'AKARI N160': 15.0, 'AKARI N60': 15.0, 'AKARI WIDE-L': 15.0,
    'AKARI WIDE-S': 15.0,
    'BAT SNR 100-150': 300.0, 'BAT SNR 14-195': 300.0, 'BAT SNR 14-20': 300.0,
    'BAT SNR 150-195': 300.0, 'BAT SNR 20-24': 300.0, 'BAT SNR 24-35': 300.0,
    'BAT SNR 35-50': 300.0, 'BAT SNR 50-75': 300.0, 'BAT SNR 75-100': 300.0,
    'CDFS: LESS': 6.07412889,
    'CFHTLS-D-g': 0.10062, 'CFHTLS-D-i': 0.10062, 'CFHTLS-D-r': 0.10062,
    'CFHTLS-D-u': 0.10062, 'CFHTLS-D-z': 0.10062, 'CFHTLS-W-g': 0.201276,
    'CFHTLS-W-i': 0.201276, 'CFHTLS-W-r': 0.201276, 'CFHTLS-W-u': 0.201276,
    'CFHTLS-W-z': 0.201276,
    'CO': 450.0,
    'COBE DIRBE/AAM': 1265.6268, 'COBE DIRBE/ZSMA': 1265.6268,
    'COMPTEL': 3600.0,
    'DSS': 1.7, 'DSS1 Blue': 1.7, 'DSS1 Red': 1.7, 'DSS2 Blue': 1.0,
    'DSS2 IR': 1.0, 'DSS2 Red': 1.0,
    'EBHIS': 195.3828,
    'EGRET (3D)': 1800.0, 'EGRET <100 MeV': 1800.0, 'EGRET >100 MeV': 1800.0,
    'EUVE 171 A': 90.0, 'EUVE 405 A': 90.0, 'EUVE 555 A': 90.0,
    'EUVE 83 A': 90.0,
    'Fermi 1': 360.0, 'Fermi 2': 360.0, 'Fermi 3': 360.0, 'Fermi 4': 360.0,
    'Fermi 5': 360.0,
    'GALEX Far UV': 1.5, 'GALEX Near UV': 1.5,
    'GB6 (4850MHz)': 40.0,
    'GLEAM 103-134 MHz': 44.0, 'GLEAM 139-170 MHz': 34.0,
    'GLEAM 170-231 MHz': 28.0, 'GLEAM 72-103 MHz': 56.0,
    'GOODS: Chandra ACIS FB': 0.492, 'GOODS: Chandra ACIS HB': 0.492,
    'GOODS: Chandra ACIS SB': 0.492,
    'GOODS: HST ACS B': 0.03, 'GOODS: HST ACS I': 0.03,
    'GOODS: HST ACS V': 0.03, 'GOODS: HST ACS Z': 0.03,
    'GOODS: HST NICMOS': 0.1,
    'GOODS: Herschel 100': 1.2, 'GOODS: Herschel 160': 2.4,
    'GOODS: Herschel 250': 3.6, 'GOODS: Herschel 350': 4.8,
    'GOODS: Herschel 500': 7.2,
    'GOODS: Spitzer IRAC 3.6': 0.6, 'GOODS: Spitzer IRAC 4.5': 0.6,
    'GOODS: Spitzer IRAC 5.8': 0.6, 'GOODS: Spitzer IRAC 8.0': 0.6,
    'GOODS: Spitzer MIPS 24': 1.2,
    'GOODS: VLA North': 0.5,
    'GOODS: VLT ISAAC H': 0.15, 'GOODS: VLT ISAAC J': 0.15,
    'GOODS: VLT ISAAC Ks': 0.15, 'GOODS: VLT VIMOS R': 0.205,
    'GOODS: VLT VIMOS U': 0.205,
    'GRANAT/SIGMA': 194.8674456,
    'H-Alpha Comp': 150.0,
    'HEAO 1 A-2': 900.0,
    'HI4PI': 90.0,
    'HRI': 5.04,
    'HUDF: VLT ISAAC Ks': 0.15,
    'Hawaii HDF B': 0.3, 'Hawaii HDF HK': 0.3, 'Hawaii HDF I': 0.3,
    'Hawaii HDF R': 0.3, 'Hawaii HDF U': 0.3, 'Hawaii HDF V0201': 0.3,
    'Hawaii HDF V0401': 0.3, 'Hawaii HDF z': 0.3,
    'INT GAL 17-35 Flux': 240.40488, 'INT GAL 17-60 Flux': 240.40488,
    'INT GAL 35-80 Flux': 240.40488,
    'INTEGRAL/SPI GC': 360.0,
    'IRAS  12 micron': 90.0, 'IRAS  25 micron': 90.0, 'IRAS  60 micron': 90.0,
    'IRAS 100 micron': 90.0, 'IRIS  12': 90.0, 'IRIS  25': 90.0,
    'IRIS  60': 90.0, 'IRIS 100': 90.0,
    'Mellinger Blue': 36.0, 'Mellinger Green': 36.0, 'Mellinger Red': 36.0,
    'NEAT': 1.44,
    'NVSS': 15.000372,
    'PSPC 0.6 Deg-Int': 15.0, 'PSPC 1.0 Deg-Int': 15.0,
    'PSPC 2.0 Deg-Int': 15.0,
    'Planck 030': 108.0, 'Planck 044': 108.0, 'Planck 070': 108.0,
    'Planck 100': 108.0, 'Planck 143': 108.0, 'Planck 217': 108.0,
    'Planck 353': 108.0, 'Planck 545': 108.0, 'Planck 857': 108.0,
    'RASS Background 1': 720.0, 'RASS Background 2': 720.0,
    'RASS Background 3': 720.0, 'RASS Background 4': 720.0,
    'RASS Background 5': 720.0, 'RASS Background 6': 720.0,
    'RASS Background 7': 720.0,
    'RASS-Cnt Broad': 45.0, 'RASS-Cnt Hard': 45.0, 'RASS-Cnt Soft': 45.0,
    'ROSAT WFC F1': 60.0, 'ROSAT WFC F2': 60.0,
    'RXTE Allsky 3-20keV Flux': 1800.0, 'RXTE Allsky 3-8keV Flux': 1800.0,
    'RXTE Allsky 8-20keV Flux': 1800.0,
    'SDSSdr7g': 0.396, 'SDSSdr7i': 0.396, 'SDSSdr7r': 0.396, 'SDSSdr7u': 0.396,
    'SDSSdr7z': 0.396, 'SDSSg': 0.396, 'SDSSi': 0.396, 'SDSSr': 0.396,
    'SDSSu': 0.396, 'SDSSz': 0.396,
    'SFD Dust Map': 142.4328444,
    'SFD100m': 142.4328444,
    'SHASSA C': 47.39976, 'SHASSA CC': 47.39976, 'SHASSA H': 47.39976,
    'SHASSA Sm': 47.39976,
    'SUMSS 843 MHz': 12.6,
    'Stripe82VLA': 0.6,
    'SwiftXRTCnt': 3.6, 'SwiftXRTExp': 3.6, 'SwiftXRTInt': 3.6,
    'TGSS ADR1': 6.2,
    'UKIDSS-H': 0.40104, 'UKIDSS-J': 0.40104, 'UKIDSS-K': 0.40104,
    'UKIDSS-Y': 0.40104,
    'UVOT B Intensity': 1.0, 'UVOT U Intensity': 1.0,
    'UVOT UVM2 Intensity': 1.0, 'UVOT UVW1 Intensity': 1.0,
    'UVOT UVW2 Intensity': 1.0, 'UVOT V Intensity': 1.0,
    'UVOT WHITE Intensity': 1.0,
    'UltraVista-H': 1.0, 'UltraVista-J': 1.0, 'UltraVista-Ks': 1.0,
    'UltraVista-NB118': 1.0, 'UltraVista-Y': 1.0,
    'VLA FIRST (1.4 GHz)': 1.8,
    'VLSSr': 20.0,
    'WENSS': 21.093732,
    'WISE 12': 1.37484, 'WISE 22': 1.37484, 'WISE 3.4': 1.37484,
    'WISE 4.6': 1.37484,
    'WMAP ILC': 632.52, 'WMAP K': 632.52, 'WMAP Ka': 632.52, 'WMAP Q': 632.52,
    'WMAP V': 632.52, 'WMAP W': 632.52,
    'nH': 2430.0,
}

default_size = 1024
