# Licensed under the GPLv3 - see LICENSE
"""Wrappers for PSRFTIS Header Data Units (HDUs)."""
from collections import namedtuple

import astropy.units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord, EarthLocation
from astropy.coordinates import Angle, Latitude, Longitude
from astropy.io import fits
from astropy.utils import lazyproperty
import numpy as np


__all__ = ["HDU_map", "HDUWrapper", "PSRFITSPrimaryHDU",
           "SubintHDU", "PSRSubintHDU"]


class HDUWrapper:
    def __init__(self, hdu, verify=True):
        self.hdu = hdu
        if verify:
            self.verify()

    def verify(self):
        assert isinstance(self.header, fits.Header)

    @property
    def header(self):
        return self.hdu.header

    @property
    def data(self):
        return self.hdu.data

    def close(self):
        del self.hdu.data
        del self.hdu


class PSRFITSPrimaryHDU(HDUWrapper):
    """Wrapper for PSRFITS primary HDU, providing baseband-style properties.

    Parameters
    ----------
    hdu : `~astropy.io.fits.PrimaryHDU`
        PSRFITS primary HDU instance.

    Notes
    -----
    Frequencies are defined to be in the center of the channels.
    """

    _properties = ('location', 'start_time', 'observatory', 'frequency',
                   'ra', 'dec', 'shape', 'sample_rate')

    def verify(self):
        assert self.header['SIMPLE'], "The HDU is not a FITS primary HDU."
        assert self.header['FITSTYPE'] == "PSRFITS", \
            "The header is not from a PSRFITS file."

    @property
    def location(self):
        try:
            return EarthLocation(self.header['ANT_X'],
                                 self.header['ANT_Y'],
                                 self.header['ANT_Z'], u.m)
        except KeyError:
            return None

    @property
    def start_time(self):
        return (Time(self.header['STT_IMJD'], format='mjd', precision=9,
                     location=self.location) +
                TimeDelta(self.header['STT_SMJD'], self.header['STT_OFFS'],
                          format='sec', scale='tai'))

    @property
    def observatory(self):
        return self.header['TELESCOP']

    @property
    def frequency(self):
        try:
            n_chan = self.header['OBSNCHAN']
            c_freq = self.header['OBSFREQ']
            bw = self.header['OBSBW']
        except KeyError:
            return None

        chan_bw = bw / n_chan
        # According to the PSRFITS definition document, channels are
        # numbered 1 to n_chan, with the zeroth channel assumed removed
        # and c_freq is the frequency of channel n_nchan / 2.  We use
        # (n_chan + 1) // 2 to ensure this makes sense for n_chan = 1
        # and is consistent with the document at least for even n_chan.
        freq = c_freq + (np.arange(1, n_chan + 1) -
                         ((n_chan + 1) // 2)) * chan_bw
        return u.Quantity(freq, u.MHz, copy=False)

    @property
    def ra(self):
        return Longitude(self.header['RA'], unit=u.hourangle)

    @property
    def dec(self):
        return Latitude(self.header['DEC'], unit=u.deg)

    @property
    def obs_mode(self):
        return self.header['OBS_MODE']


class SubintHDU(HDUWrapper):
    """Base for PSRFITS SUBINT HDU wrappers.

    Parameters
    ----------
    hdu : `~astropy.io.fits.BinTableHDU` instance
        The PSRFITS table HDU of SUBINT type.
    primary : `~scintillometry.io.psrfits.PSRFITSPrimaryHDU`
        The wrapped PSRFITS main header.
    verify: bool, optional
        Whether to do basic verification.  Default is `True`.

    Notes
    -----
    Right now we are assuming the data rows are continuous in time and the
    frequencies do not vary.
    """

    _properties = ('start_time', 'sample_rate', 'sample_shape',
                   'shape', 'samples_per_frame',
                   'polarization', 'frequency')

    _sample_shape_maker = namedtuple('SampleShape', 'nbin, nchan, npol')
    _shape_maker = namedtuple('Shape', 'nsample, nbin, nchan, npol')

    def __new__(cls, hdu, primary_hdu, verify=True):
        # Map Subint subclasses;
        # TODO: switch to__init_subclass__ when we only support python>=3.6.
        mode = primary_hdu.obs_mode
        try:
            cls = subint_map[mode]
        except KeyError:
            raise ValueError("'{}' is not a valid mode.".format(mode))

        return super().__new__(cls)

    def __init__(self, hdu, primary_hdu, verify=True):
        self.primary_hdu = primary_hdu
        self.offset = 0
        super().__init__(hdu, verify=verify)

    def verify(self):
        assert self.header['EXTNAME'].strip() == "SUBINT", \
            "Input HDU is not a SUBINT type."
        assert isinstance(self.primary_hdu, PSRFITSPrimaryHDU), \
            "Primary HDU needs to be a PSRFITSPrimaryHDU instance."

    @property
    def mode(self):
        return self.primary_hdu.obs_mode

    @property
    def start_time(self):
        # Note: subclasses can use or override this.
        return self.primary_hdu.start_time

    @property
    def nrow(self):
        return self.header['NAXIS2']

    @property
    def nchan(self):
        return self.header['NCHAN']

    @property
    def npol(self):
        return self.header['NPOL']

    @property
    def nbin(self):
        return self.header['NBIN']

    @property
    def sample_shape(self):
        return self._sample_shape_maker(self.nbin, self.nchan, self.npol)

    @property
    def shape(self):
        return self._shape_maker(self.nrow * self.samples_per_frame,
                                 self.nbin, self.nchan, self.npol)

    @property
    def polarization(self):
        pol_type = self.header['POL_TYPE']
        # split into equal parts using zip;
        # see https://docs.python.org/3.5/library/functions.html#zip
        return np.array([map(''.join, zip(*[iter(self.header['POL_TYPE'])] *
                                          (len(pol_type) // self.npol)))])

    @property
    def frequency(self):
        if 'DAT_FREQ' in self.data.names:
            freqs = u.Quantity(self.data['DAT_FREQ'],
                               u.MHz, copy=False)[0]
        else:
            freqs = super().frequency

        if freqs is not None:
            freqs = freqs.reshape(-1, 1)

        return freqs

    @lazyproperty
    def dtype(self):
        """Data type of the data.  Inferred from ``read_data_row(0)``."""
        return self.read_data_row(0).dtype

    def read_data_row(self, index, weighted=False):
        if index >= self.nrow:
            raise EOFError("cannot read from beyond end of input SUBINT HDU.")

        row = self.data[index]
        # Reversed the header shape to match the data
        data_scale = row['DAT_SCL'].reshape(-1, 1)
        data_off_set = row['DAT_OFFS'].reshape(-1, 1)
        try:
            zero_off = self.header['ZERO_OFF']
            # Sometimes zero_off equals * or some such
            float(zero_off)
        except Exception:
            zero_off = 0
        result = (row['DATA'] - zero_off) * data_scale + data_off_set
        if weighted and 'DAT_WTS' in self.data.names:
            result *= row['DAT_WTS'].reshape(-1, 1)
        return result


class PSRSubintHDU(SubintHDU):
    """Wrapper for PSRFITS SUBINT HDUs, providing baseband-style properties.

    Parameters
    ----------
    hdu : `~astropy.io.fits.BinTableHDU` instance
        The PSRFITS table HDU of SUBINT type.
    primary : `~scintillometry.io.psrfits.PSRFITSPrimaryHDU`
        The wrapped PSRFITS main header.
    verify: bool, optional
        Whether to do basic verification.  Default is `True`.

    Notes
    -----
    Right now we are assuming the data rows are continuous in time and the
    frequency are the same.
    """
    def verify(self):
        super().verify()
        assert self.mode.upper() == 'PSR', \
            "Header HDU is not in the folding mode."

        assert int(self.header['NBIN']) > 1, \
            "Invalid 'NBIN' field in the header."

        # Check frequency
        if 'DAT_FREQ' in self.data.names:
            freqs = u.Quantity(self.data['DAT_FREQ'],
                               u.MHz, copy=False)
            assert np.array_equiv(freqs[0], freqs), \
                "Frequencies are not all the same for different rows."

        tsubint = self.data['TSUBINT']
        assert all(np.isclose(tsubint[0], tsubint, atol=1e-1)), \
            "TSUBINT differ by large amounts in different rows."

        d_shape_raw = self.data['DATA'].shape
        d_shape_header = (self.nbin, self.nchan, self.npol)
        assert d_shape_raw == (self.nrow,) + d_shape_header[::-1], \
            "Data shape does not match with the header information."

    @property
    def start_time(self):
        """Start time of the first sub-integration.

        Notes
        -----
        The start time is accurate to one pulse period. This calculation below
        is consistent with PSRCHIVE's definition
        (defined in psrchive/Base/Classes/Integration.C)
        """
        start_time = super().start_time
        if "OFFS_SUB" in self.data.names:
            offset0 = (u.Quantity(self.data['OFFS_SUB'][0], u.s, copy=False) -
                       self.samples_per_frame / 2 / self.sample_rate)
            start_time += offset0

        return start_time

    @property
    def samples_per_frame(self):
        return 1

    @property
    def sample_rate(self):
        # NOTE we are assuming TSUBINT is uniform; tested in verify,
        # but as individual numbers seem to vary, take the mean.
        # TODO: check whether there really isn't a better way!.
        sample_time = u.Quantity(self.data['TSUBINT'], u.s).mean()
        return 1.0 / sample_time

    def close(self):
        super().close()
        self.primary_hdu.close()


HDU_map = {'PRIMARY': PSRFITSPrimaryHDU,
           'SUBINT': SubintHDU}

subint_map = {'PSR': PSRSubintHDU}
