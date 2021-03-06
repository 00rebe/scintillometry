.. _fourier:

*********************************************
Fourier Transforms (`scintillometry.fourier`)
*********************************************

Introduction
============

The Fourier transform module contains classes that wrap various fast Fourier
transform (FFT) packages, in particular `numpy.fft` and `pyfftw.FFTW`.  The
purpose of the module is to give the packages a common interface, and to allow
individual transforms to be defined once, then re-used multiple times.  This is
especially useful for FFTW, which achieves its fast transforms through prior
planning.

The module currently does not support Hermitian Fourier transforms -
frequency-domain values are always treated as complex.

.. _fourier_usage:

Using the Fourier Module
========================

To get an FFT maker, we may use the `~scintillometry.fourier.base.get_fft_maker`
function::

    >>> from scintillometry import fourier
    >>> FFTMaker = fourier.get_fft_maker('numpy')

`~scintillometry.fourier.base.get_fft_maker` returns an instance of one of the
FFT maker classes - e.g. `~scintillometry.fourier.numpy.NumpyFFTMaker` or
`~scintillometry.fourier.pyfftw.PyfftwFFTMaker`.  Package-level options,
such as the flags to `~pyfftw.FFTW`, can be passed as ``**kwargs``.

To create a transform, we pass the time-dimension data array shape and dtype,
transform direction ('forward' or 'backward'), transform axis (if the data is
multi-dimensional), normalization convention and sample rate to ``FFTMaker``::

    >>> import numpy as np
    >>> import astropy.units as u
    >>> fft = FFTMaker((1000,), 'float64', direction='forward', ortho=True,
    ...                sample_rate=1.*u.kHz)

Here, we have chosen orthogonal normalization, which normalizes both the
frequency and time-domain outputs by :math:`1 / n^{1/2}`, where :math:`n` is
the length of the time-domain array.  We can now perform the transform by
calling ``fft``::

    >>> y = np.sin(2. * np.pi * np.arange(1000))
    >>> Y = fft(y)

``Y`` is the Fourier transform of ``y``.  To obtain the inverse, we use the
``inverse`` method in ``fft``::

    >>> ifft = fft.inverse()
    >>> y_copy = y.copy()
    >>> yn = ifft(Y)
    >>> np.allclose(y, y_copy)
    True

Note that we compare to a copy of the input; if possible for a given
Fourier implementation (e.g., in ``pyfftw` but not in `numpy`), the ``inverse``
implementation reuses input and output arrays of the forward transform to
save memory, so at the end on would have ``yn is y``.

To show information about the transform, we can simply print the instance::

    >>> fft
    <NumpyFFT direction=forward,
        axis=0, ortho=True, sample_rate=1.0 kHz
        Time domain: shape=(1000,), dtype=float64
        Frequency domain: shape=(501,), dtype=complex128>

To obtain the sample frequencies of ``Y``, we can use the
`~scintillometry.fourier.base.FFTBase.frequency` property::

    >>> fft.frequency[:10]  # doctest: +FLOAT_CMP
    <Quantity [0.   , 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008,
           0.009] kHz>

For multi-dimensional arrays, the sample frequencies are for the transformed
axis.

.. _fourier_api:

Reference/API
=============

.. automodapi:: scintillometry.fourier
   :include-all-objects:
.. automodapi:: scintillometry.fourier.base
   :include-all-objects:
.. automodapi:: scintillometry.fourier.numpy
.. automodapi:: scintillometry.fourier.pyfftw
