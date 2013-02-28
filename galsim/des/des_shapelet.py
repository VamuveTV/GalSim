# Copyright 2012, 2013 The GalSim developers:
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
#
# GalSim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GalSim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GalSim.  If not, see <http://www.gnu.org/licenses/>
#
"""@file des_psf.py

Part of the DES module.  This file implements two ways that DES measures the PSF.

The DES_Shapelet class handles interpolated shapelet decompositions, which are generally
stored in *_fitpsf.fits files.

The DES_PsfEx class handles interpolated PCA images, which are generally stored in 
*_psfcat.psf files.
"""

import galsim

class DES_Shapelet(object):
    """Class that handles DES files describing interpolated shapelet decompositions.
    These are usually stored as *_fitpsf.fits files, although there is also an ASCII
    version stored as *_fitpsf.dat.

    Typical usage:
        
        des_shapelet = galsim.des.DES_Shapelet(fitpsf_file_name)
        
        ...

        pos = galsim.Position(image_x, image_y)  # position in pixels on the image
                                                 # NOT in arcsec on the sky!
        psf = des_shapelet.getPSF(pos)

    This class will only interpolate within the defining bounds.  It won't extrapolate
    beyond the bounding box of where the stars defined the interpolation.
    If you try to use it with an invalid position, it will throw an IndexError.
    You can check whether a position is valid with

        if des_shapelet.bounds.includes(pos):
            psf = des_shapelet.getPSF(pos)
        else:
            [...skip this object...]


    @param file_name  The file name to be read in.
    @param file_type  Either 'ASCII' or 'FITS' or None.  If None, infer from the file name ending
                      (default = None).
    """
    _req_params = { 'file_name' : str }
    _opt_params = { 'file_type' : str }
    _single_params = []
    _takes_rng = False

    def __init__(self, file_name, file_type=None):

        self.file_name = file_name.strip()

        if not file_type:
            if self.file_name.lower().endswith('.fits'):
                file_type = 'FITS'
            else:
                file_type = 'ASCII'
        file_type = file_type.upper()
        if file_type not in ['FITS', 'ASCII']:
            raise ValueError("file_type must be either FITS or ASCII if specified.")

        try:
            if file_type == 'FITS':
                self.read_fits()
            else:
                self.read_ascii()
        except Exception, e:
            print e
            raise RuntimeError("Unable to read %s DES_Shapelet file %s."%(
                    file_type,self.file_name))

    def read_ascii(self):
        import numpy
        fin = open(self.file_name, 'r')
        lines = fin.readlines()
        temp = lines[0].split()
        self.psf_order = int(temp[0])
        self.psf_size = (self.psf_order+1) * (self.psf_order+2) / 2
        self.sigma = float(temp[1])
        self.fit_order = int(temp[2])
        self.fit_size = (self.fit_order+1) * (self.fit_order+2) / 2
        self.npca = int(temp[3])

        temp = lines[1].split()
        self.bounds = galsim.BoundsD(
            float(temp[0]), float(temp[1]),
            float(temp[2]), float(temp[3]))

        temp = lines[2].split()
        assert int(temp[0]) == self.psf_size
        self.ave_psf = numpy.array(temp[2:self.psf_size+2]).astype(float)
        assert self.ave_psf.shape == (self.psf_size,)

        temp = lines[3].split()
        assert int(temp[0]) == self.npca
        assert int(temp[1]) == self.psf_size
        self.rot_matrix = numpy.array(
            [ lines[4+k].split()[1:self.psf_size+1] for k in range(self.npca) ]
            ).astype(float)
        assert self.rot_matrix.shape == (self.npca, self.psf_size)

        temp = lines[5+self.npca].split()
        assert int(temp[0]) == self.fit_size
        assert int(temp[1]) == self.npca
        self.interp_matrix = numpy.array(
            [ lines[6+self.npca+k].split()[1:self.npca+1] for k in range(self.fit_size) ]
            ).astype(float)
        assert self.interp_matrix.shape == (self.fit_size, self.npca)

    def read_fits(self):
        import pyfits
        cat = pyfits.getdata(self.file_name,1)
        # These fields each only contain one element, hence the [0]'s.
        self.psf_order = cat.field('psf_order')[0]
        self.psf_size = (self.psf_order+1) * (self.psf_order+2) / 2
        self.sigma = cat.field('sigma')[0]
        self.fit_order = cat.field('fit_order')[0]
        self.fit_size = (self.fit_order+1) * (self.fit_order+2) / 2
        self.npca = cat.field('npca')[0]

        self.bounds = galsim.BoundsD(
            float(cat.field('xmin')[0]), float(cat.field('xmax')[0]),
            float(cat.field('ymin')[0]), float(cat.field('ymax')[0]))

        self.ave_psf = cat.field('ave_psf')[0]
        assert self.ave_psf.shape == (self.psf_size,)

        self.rot_matrix = cat.field('rot_matrix')[0].T
        assert self.rot_matrix.shape == (self.npca, self.psf_size)

        self.interp_matrix = cat.field('interp_matrix')[0].T
        assert self.interp_matrix.shape == (self.fit_size, self.npca)

    def getPSF(self, pos):
        """Returns the PSF at position pos

        This returns a Shapelet instance.
        """
        if not self.bounds.includes(pos):
            raise IndexError("position in DES_Shapelet.getPSF is out of bounds")

        import numpy
        Px = self._definePxy(pos.x,self.bounds.xmin,self.bounds.xmax)
        Py = self._definePxy(pos.y,self.bounds.ymin,self.bounds.ymax)
        P = numpy.zeros(self.fit_size)
        i = 0
        for n in range(self.fit_order+1):
            for q in range(n):
                P[i] = Px[n-q] * Py[q]
                i = i+1

        b1 = numpy.dot(P,self.interp_matrix)
        b = numpy.dot(b1,self.rot_matrix)
        assert len(b) == self.psf_size
        b += self.ave_psf
        return galsim.Shapelet(self.sigma, self.psf_order, b)

    def _definePxy(self, x, min, max):
        import numpy
        x1 = (2.*x-min-max)/(max-min)
        temp = numpy.ones(self.fit_order+1)
        if self.fit_order > 0:
            temp[1] = x1
        for i in range(2,self.fit_order):
            temp[i] = ((2.*i-1.)*x1*temp[i-1] - (i-1.)*temp[i-2]) / float(i)
        return temp

