# Copyright (c) 2012-2019 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#

from __future__ import print_function
import os
import sys
import numpy as np

import galsim
from galsim_test_helpers import *


def check_dep(f, *args, **kwargs):
    """Check that some function raises a GalSimDeprecationWarning as a warning, but not an error.
    """
    # Check that f() raises a warning, but not an error.
    with assert_warns(galsim.GalSimDeprecationWarning):
        res = f(*args, **kwargs)
    return res


@timer
def test_gsparams():
    check_dep(galsim.GSParams, allowed_flux_variation=0.90)
    check_dep(galsim.GSParams, range_division_for_extrema=50)
    check_dep(galsim.GSParams, small_fraction_of_flux=1.e-6)


@timer
def test_phase_psf():
    atm = galsim.Atmosphere(screen_size=10.0, altitude=0, r0_500=0.15, suppress_warning=True)
    psf = atm.makePSF(exptime=0.02, time_step=0.01, diam=1.1, lam=1000.0)
    check_dep(galsim.PhaseScreenPSF.__getattribute__, psf, "img")
    check_dep(galsim.PhaseScreenPSF.__getattribute__, psf, "finalized")

@timer
def test_interpolant():
    d = check_dep(galsim.Delta, tol=1.e-2)
    assert d.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, d, 'tol') == d.gsparams.kvalue_accuracy
    n = check_dep(galsim.Nearest, tol=1.e-2)
    assert n.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, n, 'tol') == n.gsparams.kvalue_accuracy
    s = check_dep(galsim.SincInterpolant, tol=1.e-2)
    assert s.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, s, 'tol') == s.gsparams.kvalue_accuracy
    l = check_dep(galsim.Linear, tol=1.e-2)
    assert l.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, l, 'tol') == l.gsparams.kvalue_accuracy
    c = check_dep(galsim.Cubic, tol=1.e-2)
    assert c.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, c, 'tol') == c.gsparams.kvalue_accuracy
    q = check_dep(galsim.Quintic, tol=1.e-2)
    assert q.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, q, 'tol') == q.gsparams.kvalue_accuracy
    l3 = check_dep(galsim.Lanczos, 3, tol=1.e-2)
    assert l3.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, l3, 'tol') == l3.gsparams.kvalue_accuracy
    ldc = check_dep(galsim.Lanczos, 3, False, tol=1.e-2)
    assert ldc.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, ldc, 'tol') == ldc.gsparams.kvalue_accuracy
    l8 = check_dep(galsim.Lanczos, 8, tol=1.e-2)
    assert l8.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, l8, 'tol') == l8.gsparams.kvalue_accuracy
    l11 = check_dep(galsim.Interpolant.from_name, 'lanczos11', tol=1.e-2)
    assert l11.gsparams.kvalue_accuracy == 1.e-2
    assert check_dep(getattr, l11, 'tol') == l11.gsparams.kvalue_accuracy

@timer
def test_noise():
    real_gal_dir = os.path.join('..','examples','data')
    real_gal_cat = 'real_galaxy_catalog_23.5_example.fits'
    real_cat = galsim.RealGalaxyCatalog(
        dir=real_gal_dir, file_name=real_gal_cat, preload=True)

    test_seed=987654
    test_index = 17
    cf_1 = real_cat.getNoise(test_index, rng=galsim.BaseDeviate(test_seed))
    im_2, pix_scale_2, var_2 = real_cat.getNoiseProperties(test_index)
    # Check the variance:
    var_1 = cf_1.getVariance()
    assert var_1==var_2,'Inconsistent noise variance from getNoise and getNoiseProperties'
    # Check the image:
    ii = galsim.InterpolatedImage(im_2, normalization='sb', calculate_stepk=False,
                                  calculate_maxk=False, x_interpolant='linear')
    cf_2 = check_dep(galsim.correlatednoise._BaseCorrelatedNoise,
                     galsim.BaseDeviate(test_seed), ii, im_2.wcs)
    cf_2 = cf_2.withVariance(var_2)
    assert cf_1==cf_2,'Inconsistent noise properties from getNoise and getNoiseProperties'

@timer
def test_randwalk_defaults():
    """
    Create a random walk galaxy and test that the getters work for
    default inputs
    """

    # try constructing with mostly defaults
    npoints=100
    hlr = 8.0
    rng = galsim.BaseDeviate(1234)
    rw=check_dep(galsim.RandomWalk, npoints, half_light_radius=hlr, rng=rng)

    assert rw.npoints==npoints,"expected npoints==%d, got %d" % (npoints, rw.npoints)
    assert rw.input_half_light_radius==hlr,\
        "expected hlr==%g, got %g" % (hlr, rw.input_half_light_radius)

    nobj=len(rw.points)
    assert nobj == npoints,"expected %d objects, got %d" % (npoints, nobj)

    pts=rw.points
    assert pts.shape == (npoints,2),"expected (%d,2) shape for points, got %s" % (npoints, pts.shape)
    np.testing.assert_almost_equal(rw.centroid.x, np.mean(pts[:,0]))
    np.testing.assert_almost_equal(rw.centroid.y, np.mean(pts[:,1]))

    gsp = galsim.GSParams(xvalue_accuracy=1.e-8, kvalue_accuracy=1.e-8)
    rng2 = galsim.BaseDeviate(1234)
    rw2 = check_dep(galsim.RandomWalk, npoints, half_light_radius=hlr, rng=rng2, gsparams=gsp)
    assert rw2 != rw
    assert rw2 == rw.withGSParams(gsp)

    # Check that they produce identical images.
    psf = galsim.Gaussian(sigma=0.8)
    conv1 = galsim.Convolve(rw.withGSParams(gsp), psf)
    conv2 = galsim.Convolve(rw2, psf)
    im1 = conv1.drawImage()
    im2 = conv2.drawImage()
    assert im1 == im2

    # Check that image is not sensitive to use of rng by other objects.
    rng3 = galsim.BaseDeviate(1234)
    rw3=check_dep(galsim.RandomWalk, npoints, half_light_radius=hlr, rng=rng3)
    rng3.discard(523)
    conv1 = galsim.Convolve(rw, psf)
    conv3 = galsim.Convolve(rw3, psf)
    im1 = conv1.drawImage()
    im3 = conv2.drawImage()
    assert im1 == im3

    # Run some basic tests of correctness
    check_basic(conv1, "RandomWalk")
    im = galsim.ImageD(64,64, scale=0.5)
    do_shoot(conv1, im, "RandomWalk")
    do_kvalue(conv1, im, "RandomWalk")
    do_pickle(rw)
    do_pickle(conv1)
    do_pickle(conv1, lambda x: x.drawImage(scale=1))


@timer
def test_randwalk_repr():
    """
    test the repr and str work, and that a new object can be created
    using eval
    """

    npoints=100
    hlr = 8.0
    flux=1
    rw1=check_dep(galsim.RandomWalk,
        npoints,
        half_light_radius=hlr,
        flux=flux,
    )
    rw2=check_dep(galsim.RandomWalk,
        npoints,
        profile=galsim.Exponential(half_light_radius=hlr, flux=flux),
    )

    for rw in (rw1, rw2):


        # just make sure str() works, don't require eval to give
        # a consistent object back
        st=str(rw)

        # require eval(repr(rw)) to give a consistent object back

        new_rw = eval(repr(rw))

        assert new_rw.npoints == rw.npoints,\
            "expected npoints=%d got %d" % (rw.npoints,new_rw.npoints)

        mess="expected input_half_light_radius=%.16g got %.16g"
        assert new_rw.input_half_light_radius == rw.input_half_light_radius,\
            mess % (rw.input_half_light_radius,new_rw.input_half_light_radius)
        assert new_rw.flux == rw.flux,\
            "expected flux=%.16g got %.16g" % (rw.flux,new_rw.flux)

@timer
def test_randwalk_config():
    """
    test we get the same object using a configuration and the
    explicit constructor
    """

    hlr=2.0
    flux=np.pi
    gal_config1 = {
        'type':'RandomWalk',
        'npoints':100,
        'half_light_radius':hlr,
        'flux':flux,
    }
    gal_config2 = {
        'type':'RandomWalk',
        'npoints':150,
        'profile': {
            'type': 'Exponential',
            'half_light_radius': hlr,
            'flux': flux,
        }
    }

    for gal_config in (gal_config1, gal_config2):
        config={
            'gal':gal_config,
            'rng':galsim.BaseDeviate(31415),
        }

        rwc = check_dep(galsim.config.BuildGSObject, config, 'gal')[0]
        print(repr(rwc._profile))

        rw = check_dep(galsim.RandomWalk,
            gal_config['npoints'],
            half_light_radius=hlr,
            flux=flux,
        )

        assert rw.npoints==rwc.npoints,\
            "expected npoints==%d, got %d" % (rw.npoints, rwc.npoints)

        assert rw.input_half_light_radius==rwc.input_half_light_radius,\
            "expected hlr==%g, got %g" % (rw.input_half_light_radius, rw.input_half_light_radius)

        nobj=len(rw.points)
        nobjc=len(rwc.points)
        assert nobj==nobjc,"expected %d objects, got %d" % (nobj,nobjc)

        pts=rw.points
        ptsc=rwc.points
        assert (pts.shape == ptsc.shape),\
                "expected %s shape for points, got %s" % (pts.shape,ptsc.shape)


if __name__ == "__main__":
    test_gsparams()
    test_phase_psf()
    test_interpolant()
    test_noise()
    test_randwalk_defaults()
    test_randwalk_repr()
    test_randwalk_config()
