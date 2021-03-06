# Licensed under the GPLv3 - see LICENSE
"""Interfaces for dealing with PSRFITS fold-mode data."""

from ...base import BaseTaskBase
from astropy.io import fits
from .hdu import HDU_map
from astropy import log
from collections import defaultdict


__all__ = ['open', 'get_readers', 'PSRFITSReader']


def open(filename, mode='r', **kwargs):
    """Function to open a PSRFITS file.

    Parameters
    ----------
    filename : str
        Input PSRFITS file name.
    mode : str
        Open mode, currently, it only supports 'r'/'read' mode.
    **kwargs
        Additional arguments for opening the fits file and creating the reader.

    --- For opening the fits file :

    memmap : bool, optional
        Is memory mapping to be used? By default, this value is obtained from
        the configuration item ``astropy.io.fits.Conf.use_memmap`` (the
        default of which, in turn, is `True`).

    --- For creating the reader :

    weighted :  bool, optional
        Whether the data should be weighted along the frequency axis.
        Default is `True`.
    verify : bool, optional
        Whether to do basic checks on the PSRFITS HDUs.
        Default is `True`.

    Returns
    -------
    reader : file-handle like reader for the first SUBINT HDU

    Raises
    ------
    RuntimeError
        If more than one SUBINT HDU is present.

    Notes
    -----
    The current version` only opens and reads one SUBINT HDU and ignores all
    other types of HDUs.
    """
    if mode == 'r':
        memmap = kwargs.pop('memmap', None)
        hdu_list = fits.open(filename, 'readonly', memmap=memmap)
        reader_list = get_readers(hdu_list, **kwargs)
        # TODO: allow support for more than one HDU.
        if len(reader_list) != 1:
            raise RuntimeError("Current reader can only read one SUBINT HDU.")
        return reader_list[0]
    else:
        raise ValueError("Unknown mode '{}'. Currently only 'r' mode are"
                         " supported.".format(mode))


def get_readers(hdu_list, **kwargs):
    """Function to read one PSRFITS file into a list of HDU Readers.

    Parameters
    ----------
    hdu_list : str
        Opened PSRFITS file.
    **kwargs
        Additional arguments for opening the fits file and creating the reader.
        Passes on to `~scintillometry.io.psrfits.PSRFITSReader`.

    Returns
    -------
    readers : list of the HDU readers.
    """
    buffers = defaultdict(list)
    for ii, hdu in enumerate(hdu_list):
        if hdu.name in HDU_map.keys():
            buffers[hdu.name].append(hdu)
        else:
            log.warning("Skipping HDU {} ({}), as it is not a supported PSRFITS"
                        " HDU.".format(ii, hdu.name))

    primary = buffers.pop('PRIMARY', [])
    if len(primary) != 1:
        raise ValueError("HDUList `{}` does not have a header"
                         " HDU or have more than one header"
                         " HDU.".format(hdu_list))
    primary_hdu = HDU_map['PRIMARY'](primary[0])
    psrfits_hdus = []
    for k, v in buffers.items():
        for hdu in v:
            psrfits_hdus.append(HDU_map[k](hdu, primary_hdu))

    # Build reader on the HDUs
    readers = []
    for hdu in psrfits_hdus:
        readers.append(PSRFITSReader(hdu, **kwargs))

    return readers


class PSRFITSReader(BaseTaskBase):
    """Wrapper for reading PSRFITS HDUs.

    Parameters
    ----------
    ih : wrapped PSRFITS HDU
        The input fits table HDU, wrapped in an interface from
        `~scintillometry.io.psrfits`.
    frequency : `~astropy.units.Quantity`, optional
        Frequencies for each channel.  Should be broadcastable to the
        sample shape.  Default: inferred from ``hdu``.
    sideband : array, optional
        Whether frequencies are upper (+1) or lower (-1) sideband. Should be
        broadcastable to the sample shape.  Default: inferred from ``hdu``.
    polarization : array or (nested) list of char, optional
        Polarization labels.  Should broadcast to the sample shape,
        i.e., the labels are in the correct axis.  For instance,
        ``['X', 'Y']``, or ``[['L'], ['R']]``.  Default: inferred from ``hdu``.
    dtype : `~numpy.dtype`, optional
        Dtype of the samples.  Default: inferred from ``hdu``.
    weighted : bool, optional
        Whether to weight the data along the frequency axis using the
        'DAT_WTS' column.  Default of `True` should suffice for most purposes,
        but sometimes the weights are incorrect.
    """
    # Note: this very light-weight wrapper around SubintHDU is mostly here
    # because eventually it might unify different/multiple HDUs.
    def __init__(self, ih, frequency=None, sideband=None, polarization=None,
                 dtype=None, weighted=True):
        self.weighted = weighted
        super().__init__(ih, frequency=frequency, sideband=sideband,
                         polarization=polarization, dtype=dtype)

    def _read_frame(self, frame_index):
        res = self.ih.read_data_row(frame_index, weighted=self.weighted).T
        return res.reshape((self.samples_per_frame, ) + self.sample_shape)

    def close(self):
        file = self.ih.hdu._file
        super().close()
        file.close()
