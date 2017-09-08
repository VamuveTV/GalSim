# Copyright (c) 2012-2017 by the GalSim developers team on GitHub
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
"""@file random.py
Addition of docstrings to the Random deviate classes at the Python layer and definition of the
DistDeviate class.
"""

import numpy as np
from . import _galsim

class BaseDeviate(object):
    """Base class for all the various random deviates.

    This holds the essential random number generator that all the other classes use.

    Initialization
    --------------

    All deviates take an initial `seed` argument that is used to seed the underlying random number
    generator.  It has three different kinds of behavior.

    1. An integer value can be provided to explicitly seed the random number generator with a
       particular value.  This is useful to have deterministic behavior.  If you seed with an
       integer value, the subsequent series of "random" values will be the same each time you
       run the program.

    2. A seed of 0 or None means to pick some arbitrary value that will be different each time
       you run the program.  Currently, this tries to get a seed from /dev/urandom if possible.
       If that doesn't work, then it creates a seed from the current time.  You can also get this
       behavior by omitting the seed argument entirely.  (i.e. the default is None.)

    3. Providing another BaseDeviate object as the seed will make the new Deviate share the same
       underlying random number generator as the other Deviate.  So you can make one Deviate (of
       any type), and seed it with a particular deterministic value.  Then if you pass that Deviate
       to any other one you make, they will both be using the same RNG and the series of "random"
       values will be deterministic.

    Usage
    -----

    There is not much you can do with something that is only known to be a BaseDeviate rather than
    one of the derived classes other than construct it and change the seed, and use it as an
    argument to pass to other Deviate constructors.

        >>> rng = galsim.BaseDeviate(215324)
        >>> rng()
        Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        TypeError: 'BaseDeviate' object is not callable
        >>> ud = galsim.UniformDeviate(rng)
        >>> ud()
        0.58736140513792634
        >>> ud2 = galsim.UniformDeviate(215324)
        >>> ud2()
        0.58736140513792634

    Methods
    -------

    There are a few methods that are common to all BaseDeviate classes, so we describe them here.

        dev.seed(seed)      Set a new (integer) seed value for the underlying RNG.
        dev.reset(seed)     Sever the connection to the current RNG and seed a new one (either
                            creating a new RNG if seed is an integer or connecting to an existing
                            RNG if seed is a BaseDeviate instance)
        dev.clearCache()    Clear the internal cache of the Deviate, if there is any.
        dev.duplicate()     Create a duplicate of the current Deviate, which will produce an
                            identical series of values as the original.
    """
    def __init__(self, seed=None):
        self._rng_type = _galsim.BaseDeviateImpl
        self._rng_args = ()
        self.reset(seed)

    def seed(self, seed=0):
        """Seed the pseudo-random number generator with a given integer value.

        @param seed         An int value to be used to seed the random number generator.  Using 0
                            means to generate a seed from the system. [default: 0]
        """
        if seed == int(seed):
            self._seed(int(seed))
        else:
            raise TypeError("BaseDeviate seed must be an integer.  Got %s"%seed)

    def _seed(self, seed=0):
        """Equivalent to self.seed(seed), but without any type checking.
        """
        self._rng.seed(seed)

    def reset(self, seed=None):
        """Reset the pseudo-random number generator, severing connections to any other deviates.
        Providing another BaseDeviate object as the seed connects this deviate with the other
        one, so they will both use the same underlying random number generator.

        @param seed         Something that can seed a BaseDeviate: an integer seed or another
                            BaseDeviate.  Using None means to generate a seed from the system.
                            [default: None]
        """
        if isinstance(seed, BaseDeviate):
            self._reset(seed)
        elif isinstance(seed, (str, int)):
            self._rng = self._rng_type(seed, *self._rng_args)
        elif seed is None:
            self._rng = self._rng_type(0, *self._rng_args)
        else:
            raise TypeError("BaseDeviate must be initialized with either an int or another "
                            "BaseDeviate")

    def _reset(self, rng):
        """Equivalent to self.reset(rng), but rng must be a BaseDeviate (not an int), and there
        is no type checking.
        """
        self._rng = self._rng_type(rng._rng, *self._rng_args)

    def duplicate(self):
        """Create a duplicate of the current Deviate object.  The subsequent series from each copy
        of the Deviate will produce identical values.

        Example
        _______

            >>> u = galsim.UniformDeviate(31415926)
            >>> u()
            0.17100770119577646
            >>> u2 = u.duplicate()
            >>> u()
            0.49095047544687986
            >>> u()
            0.10306670609861612
            >>> u2()
            0.49095047544687986
            >>> u2()
            0.10306670609861612
            >>> u2()
            0.13129289541393518
            >>> u()
            0.13129289541393518
        """
        ret = BaseDeviate.__new__(self.__class__)
        ret.__dict__.update(self.__dict__)
        ret._rng = self._rng.duplicate()
        return ret

    def __copy__(self):
        return self.duplicate()

    def clearCache(self):
        """Clear the internal cache of the Deviate, if any.  This is currently only relevant for
        GaussianDeviate, since it generates two values at a time, saving the second one to use for
        the next output value.
        """
        self._rng.clearCache()

    def discard(self, n):
        """Discard n values from the current sequence of pseudo-random numbers.
        """
        self._rng.discard(int(n))

    def raw(self):
        """Generate the next pseudo-random number and rather than return the appropriate kind
        of random deviate for this class, just return the raw integer value that would have been
        used to generate this value.
        """
        return self._rng.raw()

    def generate(self, array):
        """Generate many pseudo-random values, filling in the values of a numpy array.
        """
        array_1d = np.ascontiguousarray(array.ravel(),dtype=float)
        assert(array_1d.strides[0] == array_1d.itemsize)
        self._rng.generate(len(array_1d), array_1d.ctypes.data)
        if array_1d.data != array.data:
            # array_1d is not a view into the original array.  Need to copy back.
            np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')

    def add_generate(self, array):
        """Generate many pseudo-random values, adding them to the values of a numpy array.
        """
        array_1d = np.ascontiguousarray(array.ravel(),dtype=float)
        assert(array_1d.strides[0] == array_1d.itemsize)
        self._rng.add_generate(len(array_1d), array_1d.ctypes.data)
        if array_1d.data != array.data:
            # array_1d is not a view into the original array.  Need to copy back.
            np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')

    def __eq__(self, other):
        return (type(self) == type(other) and
                self._rng_type == other._rng_type and
                self._rng_args == other._rng_args and
                self.serialize() == other.serialize())

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def serialize(self):
        return self._rng.serialize()

    def _seed_repr(self):
        s = self.serialize().split(' ')
        return " ".join(s[:3])+" ... "+" ".join(s[-3:])

    def __repr__(self):
        return "galsim.BaseDeviate(%r)"%self._seed_repr()

    def __str__(self):
        return "galsim.BaseDeviate(%r)"%self._seed_repr()

class UniformDeviate(BaseDeviate):
    """Pseudo-random number generator with uniform distribution in interval [0.,1.).

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]

    Calling
    -------

    Successive calls to u() generate pseudo-random values distributed uniformly in the interval
    [0., 1.).

        >>> u = galsim.UniformDeviate(31415926)
        >>> u()
        0.17100770119577646
        >>> u()
        0.49095047544687986
    """
    def __init__(self, seed=None):
        self._rng_type = _galsim.UniformDeviateImpl
        self._rng_args = ()
        self.reset(seed)

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a uniform deviate between 0 and 1.
        """
        return self._rng.generate1()

class GaussianDeviate(BaseDeviate):
    """Pseudo-random number generator with Gaussian distribution.

    See http://en.wikipedia.org/wiki/Gaussian_distribution for further details.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param mean         Mean of Gaussian distribution. [default: 0.]
    @param sigma        Sigma of Gaussian distribution. [default: 1.; Must be > 0]

    Calling
    -------

    Successive calls to g() generate pseudo-random values distributed according to a Gaussian
    distribution with the provided `mean`, `sigma`.

        >>> g = galsim.GaussianDeviate(31415926)
        >>> g()
        0.5533754000847082
        >>> g()
        1.0218588970190354
    """
    def __init__(self, seed=None, mean=0., sigma=1.):
        if sigma < 0.:
            raise ValueError("GaussianDeviate sigma must be > 0.")
        self._rng_type = _galsim.GaussianDeviateImpl
        self._rng_args = (float(mean), float(sigma))
        self.reset(seed)

    @property
    def mean(self):
        return self._rng_args[0]

    @property
    def sigma(self):
        return self._rng_args[1]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Gaussian deviate with the given mean and sigma.
        """
        return self._rng.generate1()

    def generate_from_variance(self, array):
        """Generate many Gaussian deviate values using the existing array values as the
        variance for each.
        """
        array_1d = np.ascontiguousarray(array.ravel(), dtype=float)
        assert(array_1d.strides[0] == array_1d.itemsize)
        self._rng.generate_from_variance(len(array_1d), array_1d.ctypes.data)
        if array_1d.data != array.data:
            # array_1d is not a view into the original array.  Need to copy back.
            np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')


class BinomialDeviate(BaseDeviate):
    """Pseudo-random Binomial deviate for `N` trials each of probability `p`.

    `N` is number of 'coin flips,' `p` is probability of 'heads,' and each call returns an integer
    value where 0 <= value <= N gives the number of heads.  See
    http://en.wikipedia.org/wiki/Binomial_distribution for more information.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param N            The number of 'coin flips' per trial. [default: 1; Must be > 0]
    @param p            The probability of success per coin flip. [default: 0.5; Must be > 0]

    Calling
    -------

    Successive calls to b() generate pseudo-random integer values distributed according to a
    binomial distribution with the provided `N`, `p`.

        >>> b = galsim.BinomialDeviate(31415926, N=10, p=0.3)
        >>> b()
        2
        >>> b()
        3
    """
    def __init__(self, seed=None, N=1, p=0.5):
        self._rng_type = _galsim.BinomialDeviateImpl
        self._rng_args = (int(N), float(p))
        self.reset(seed)

    @property
    def n(self):
        return self._rng_args[0]

    @property
    def p(self):
        return self._rng_args[1]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Binomial deviate with the given n and p.
        """
        return self._rng.generate1()

class PoissonDeviate(BaseDeviate):
    """Pseudo-random Poisson deviate with specified `mean`.

    The input `mean` sets the mean and variance of the Poisson deviate.  An integer deviate with
    this distribution is returned after each call.
    See http://en.wikipedia.org/wiki/Poisson_distribution for more details.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param mean         Mean of the distribution. [default: 1; Must be > 0]

    Calling
    -------

    Successive calls to p() generate pseudo-random integer values distributed according to a Poisson
    distribution with the specified `mean`.

        >>> p = galsim.PoissonDeviate(31415926, mean=100)
        >>> p()
        94
        >>> p()
        106
    """
    def __init__(self, seed=None, mean=1.):
        self._rng_type = _galsim.PoissonDeviateImpl
        self._rng_args = (float(mean),)
        self.reset(seed)

    @property
    def mean(self):
        return self._rng_args[0]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Poisson deviate with the given mean.
        """
        return self._rng.generate1()

    def generate_from_expectation(self, array):
        """Generate many Poisson deviate values using the existing array values as the
        expectation value (aka mean) for each.
        """
        array_1d = np.ascontiguousarray(array.ravel(), dtype=float)
        assert(array_1d.strides[0] == array_1d.itemsize)
        self._rng.generate_from_expectation(len(array_1d), array_1d.ctypes.data)
        if array_1d.data != array.data:
            # array_1d is not a view into the original array.  Need to copy back.
            np.copyto(array, array_1d.reshape(array.shape), casting='unsafe')


class WeibullDeviate(BaseDeviate):
    """Pseudo-random Weibull-distributed deviate for shape parameter `a` and scale parameter `b`.

    The Weibull distribution is related to a number of other probability distributions; in
    particular, it interpolates between the exponential distribution (a=1) and the Rayleigh
    distribution (a=2).
    See http://en.wikipedia.org/wiki/Weibull_distribution (a=k and b=lambda in the notation adopted
    in the Wikipedia article) for more details.  The Weibull distribution is real valued and
    produces deviates >= 0.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param a            Shape parameter of the distribution. [default: 1; Must be > 0]
    @param b            Scale parameter of the distribution. [default: 1; Must be > 0]

    Calling
    -------

    Successive calls to p() generate pseudo-random values distributed according to a Weibull
    distribution with the specified shape and scale parameters `a` and `b`.

        >>> w = galsim.WeibullDeviate(31415926, a=1.3, b=4)
        >>> w()
        1.1038481241018219
        >>> w()
        2.957052966368049
    """
    def __init__(self, seed=None, a=1., b=1.):
        self._rng_type = _galsim.WeibullDeviateImpl
        self._rng_args = (float(a), float(b))
        self.reset(seed)

    @property
    def a(self):
        return self._rng_args[0]

    @property
    def b(self):
        return self._rng_args[1]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Weibull-distributed deviate with the given shape parameters a and b.
        """
        return self._rng.generate1()


class GammaDeviate(BaseDeviate):
    """A Gamma-distributed deviate with shape parameter `k` and scale parameter `theta`.
    See http://en.wikipedia.org/wiki/Gamma_distribution.
    (Note: we use the k, theta notation. If you prefer alpha, beta, use k=alpha, theta=1/beta.)
    The Gamma distribution is a real valued distribution producing deviates >= 0.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param k            Shape parameter of the distribution. [default: 1; Must be > 0]
    @param theta        Scale parameter of the distribution. [default: 1; Must be > 0]

    Calling
    -------

    Successive calls to p() generate pseudo-random values distributed according to a gamma
    distribution with the specified shape and scale parameters `k` and `theta`.

        >>> gam = galsim.GammaDeviate(31415926, k=1, theta=2)
        >>> gam()
        0.37508882726316
        >>> gam()
        1.3504199388358704
    """
    def __init__(self, seed=None, k=1., theta=1.):
        self._rng_type = _galsim.GammaDeviateImpl
        self._rng_args = (float(k), float(theta))
        self.reset(seed)

    @property
    def k(self):
        return self._rng_args[0]

    @property
    def theta(self):
        return self._rng_args[1]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Gamma-distributed deviate with the given k and theta.
        """
        return self._rng.generate1()


class Chi2Deviate(BaseDeviate):
    """Pseudo-random Chi^2-distributed deviate for degrees-of-freedom parameter `n`.

    See http://en.wikipedia.org/wiki/Chi-squared_distribution (note that k=n in the notation
    adopted in the Boost.Random routine called by this class).  The Chi^2 distribution is a
    real-valued distribution producing deviates >= 0.

    Initialization
    --------------

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param n            Number of degrees of freedom for the output distribution. [default: 1;
                        Must be > 0]

    Calling
    -------

    Successive calls to chi2() generate pseudo-random values distributed according to a chi-square
    distribution with the specified degrees of freedom, `n`.

        >>> chi2 = galsim.Chi2Deviate(31415926, n=7)
        >>> chi2()
        7.9182211987712385
        >>> chi2()
        6.644121724269535
    """
    def __init__(self, seed=None, n=1.):
        self._rng_type = _galsim.Chi2DeviateImpl
        self._rng_args = (float(n),)
        self.reset(seed)

    @property
    def n(self):
        return self._rng_args[0]

    def __call__(self):
        """Draw a new random number from the distribution.

        Returns a Chi2-distributed deviate with the given number of degrees of freedom.
        """
        return self._rng.generate1()


class DistDeviate(BaseDeviate):
    """A class to draw random numbers from a user-defined probability distribution.

    DistDeviate is a BaseDeviate class that can be used to draw from an arbitrary probability
    distribution.  The probability distribution passed to DistDeviate can be given one of three
    ways: as the name of a file containing a 2d ASCII array of x and P(x), as a LookupTable mapping
    x to P(x), or as a callable function.

    Once given a probability, DistDeviate creates a table of the cumulative probability and draws
    from it using a UniformDeviate.  The precision of its outputs can be controlled with the
    keyword `npoints`, which sets the number of points DistDeviate creates for its internal table
    of CDF(x).  To prevent errors due to non-monotonicity, the interpolant for this internal table
    is always linear.

    Two keywords, `x_min` and `x_max`, define the support of the function.  They must be passed if
    a callable function is given to DistDeviate, unless the function is a LookupTable, which has its
    own defined endpoints.  If a filename or LookupTable is passed to DistDeviate, the use of
    `x_min` or `x_max` will result in an error.

    If given a table in a file, DistDeviate will construct an interpolated LookupTable to obtain
    more finely gridded probabilities for generating the cumulative probability table.  The default
    `interpolant` is linear, but any interpolant understood by LookupTable may be used.  We caution
    against the use of splines because they can cause non-monotonic behavior.  Passing the
    `interpolant` keyword next to anything but a table in a file will result in an error.

    Initialization
    --------------

    Some sample initialization calls:

    >>> d = galsim.DistDeviate(function=f, x_min=x_min, x_max=x_max)

    Initializes d to be a DistDeviate instance with a distribution given by the callable function
    `f(x)` from `x=x_min` to `x=x_max` and seeds the PRNG using current time.

    >>> d = galsim.DistDeviate(1062533, function=file_name, interpolant='floor')

    Initializes d to be a DistDeviate instance with a distribution given by the data in file
    `file_name`, which must be a 2-column ASCII table, and seeds the PRNG using the integer
    seed 1062533. It generates probabilities from `file_name` using the interpolant 'floor'.

    >>> d = galsim.DistDeviate(rng, function=galsim.LookupTable(x,p))

    Initializes d to be a DistDeviate instance with a distribution given by P(x), defined as two
    arrays `x` and `p` which are used to make a callable LookupTable, and links the DistDeviate
    PRNG to the already-existing random number generator `rng`.

    @param seed         Something that can seed a BaseDeviate: an integer seed or another
                        BaseDeviate.  Using 0 means to generate a seed from the system.
                        [default: None]
    @param function     A callable function giving a probability distribution or the name of a
                        file containing a probability distribution as a 2-column ASCII table.
                        [required]
    @param x_min        The minimum desired return value (required for non-LookupTable
                        callable functions; will raise an error if not passed in that case, or if
                        passed in any other case) [default: None]
    @param x_min        The maximum desired return value (required for non-LookupTable
                        callable functions; will raise an error if not passed in that case, or if
                        passed in any other case) [default: None]
    @param interpolant  Type of interpolation used for interpolating a file (causes an error if
                        passed alongside a callable function).  Options are given in the
                        documentation for LookupTable. [default: 'linear']
    @param npoints      Number of points DistDeviate should create for its internal interpolation
                        tables. [default: 256]

    Calling
    -------

    Successive calls to d() generate pseudo-random values with the given probability distribution.

    >>> d = galsim.DistDeviate(31415926, function=lambda x: 1-abs(x), x_min=-1, x_max=1)
    >>> d()
    -0.4151921102709466
    >>> d()
    -0.00909781188974034
    """
    def __init__(self, seed=None, function=None, x_min=None,
                 x_max=None, interpolant=None, npoints=256):
        from .table import LookupTable
        from . import utilities
        from . import integ

        # Set up the PRNG
        self._rng_type = _galsim.UniformDeviateImpl
        self._rng_args = ()
        self.reset(seed)

        # Basic input checking and setups
        if function is None:
            raise TypeError('You must pass a function to DistDeviate!')

        self._function = function # Save the inputs to be used in repr
        self._interpolant = interpolant
        self._npoints = npoints
        self._xmin = x_min
        self._xmax = x_max

        # Figure out if a string is a filename or something we should be using in an eval call
        if isinstance(function, str):
            input_function = function
            import os.path
            if os.path.isfile(function):
                if interpolant is None:
                    interpolant='linear'
                if x_min or x_max:
                    raise TypeError('Cannot pass x_min or x_max alongside a '
                                    'filename in arguments to DistDeviate')
                function = LookupTable.from_file(function, interpolant=interpolant)
                x_min = function.x_min
                x_max = function.x_max
            else:
                try:
                    function = utilities.math_eval('lambda x : ' + function)
                    if x_min is not None: # is not None in case x_min=0.
                        function(x_min)
                    else:
                        # Somebody would be silly to pass a string for evaluation without x_min,
                        # but we'd like to throw reasonable errors in that case anyway
                        function(0.6) # A value unlikely to be a singular point of a function
                except Exception as e:
                    raise ValueError(
                        "String function must either be a valid filename or something that "+
                        "can eval to a function of x.\n"+
                        "Input provided: {0}\n".format(input_function)+
                        "Caught error: {0}".format(e))
        else:
            # Check that the function is actually a function
            if not (isinstance(function, LookupTable) or hasattr(function, '__call__')):
                raise TypeError('Keyword function must be a callable function or a string')
            if interpolant:
                raise TypeError('Cannot provide an interpolant with a callable function argument')
            if isinstance(function, LookupTable):
                if x_min or x_max:
                    raise TypeError('Cannot provide x_min or x_max with a LookupTable function '+
                                    'argument')
                x_min = function.x_min
                x_max = function.x_max
            else:
                if x_min is None or x_max is None:
                    raise TypeError('Must provide x_min and x_max when function argument is a '+
                                    'regular python callable function')

        # Compute the cumulative distribution function
        xarray = x_min+(1.*x_max-x_min)/(npoints-1)*np.array(range(npoints), dtype=float)
        # cdf is the cumulative distribution function--just easier to type!
        dcdf = [integ.int1d(function, xarray[i], xarray[i+1]) for i in range(npoints - 1)]
        cdf = [sum(dcdf[0:i]) for i in range(npoints)]
        # Quietly renormalize the probability if it wasn't already normalized
        total_probability = cdf[-1]
        cdf = np.array(cdf)/total_probability
        # Recompute delta CDF in case of floating-point differences in near-flat probabilities
        dcdf = np.diff(cdf)
        # Check that the probability is nonnegative
        if not np.all(dcdf >= 0):
            raise ValueError('Negative probability passed to DistDeviate: %s'%function)
        # Now get rid of points with dcdf == 0
        elif not np.all(dcdf > 0.):
            # Remove consecutive dx=0 points, except endpoints
            zeroindex = np.where(dcdf==0)[0]
            # numpy.where returns a tuple containing 1 array, which tends to be annoying for
            # indexing, so the [0] returns the actual array of interest (indices of dcdf==0).
            # Now, we want to remove consecutive dcdf=0 points, leaving the lower end.
            # Zeroindex contains the indices of all the dcdf=0 points, so we look for ones that are
            # only 1 apart; this tells us the *lower* of the two points, but we want to remove the
            # *upper*, so we add 1 to the resultant array.
            dindex = np.where(np.diff(zeroindex)==1)[0]+1
            # So dindex contains the indices of the elements of array zeroindex, which tells us the
            # indices that we might want to delete from cdf and xarray, so we delete
            # zeroindex[dindex].
            cdf = np.delete(cdf, zeroindex[dindex])
            xarray = np.delete(xarray, zeroindex[dindex])
            dcdf = np.diff(cdf)
            # Tweak the edges of dx=0 regions so function is always increasing
            for index in np.where(dcdf == 0)[0][::-1]:  # reverse in case we need to delete
                if index+2 < len(cdf):
                    # get epsilon, the smallest element where 1+eps>1
                    eps = np.finfo(cdf[index+1].dtype).eps
                    if cdf[index+2]-cdf[index+1] > eps:
                        cdf[index+1] += eps
                    else:
                        cdf = np.delete(cdf, index+1)
                        xarray = np.delete(xarray, index+1)
                else:
                    cdf = cdf[:-1]
                    xarray = xarray[:-1]
            dcdf = np.diff(cdf)
            if not (np.all(dcdf>0)):
                raise RuntimeError(
                    'Cumulative probability in DistDeviate is too flat for program to fix')

        self._inverse_cdf = LookupTable(cdf, xarray, interpolant='linear')
        self.x_min = x_min
        self.x_max = x_max

    def val(self, p):
        """
        Return the value `x` of the input function to DistDeviate such that `p` = cdf(x),
        where cdf is the cumulattive probability distribution function:

            cdf(x) = int(pdf(t), t=0..x)

        This function is typically called by self.__call__(), which generates a random p
        between 0 and 1 and calls `self.val(p)`.

        @param p    The desired cumulative probabilty p.

        @returns the corresponding x such that p = cdf(x).
        """
        if p<0 or p>1:
            raise ValueError('Cannot request cumulative probability value from DistDeviate for '
                             'p<0 or p>1!  You entered: %f'%p)
        return self._inverse_cdf(p)


    def __call__(self):
        return self.val(self._rng.generate1())

    def generate(self, array):
        """Generate many pseudo-random values, filling in the values of a numpy array.
        """
        p = np.empty_like(array)
        BaseDeviate.generate(self, p)  # Fill with unform deviate values
        np.copyto(array, self._inverse_cdf(p)) # Convert from p -> x

    def add_generate(self, array):
        """Generate many pseudo-random values, adding them to the values of a numpy array.
        """
        p = np.empty_like(array)
        BaseDeviate.generate(self, p)
        array += self._inverse_cdf(p)

    def __repr__(self):
        return ('galsim.DistDeviate(seed=%r, function=%r, x_min=%r, x_max=%r, interpolant=%r, '+
                'npoints=%r)')%(self._seed_repr(), self._function, self._xmin, self._xmax,
                                self._interpolant, self._npoints)
    def __str__(self):
        return 'galsim.DistDeviate(function="%s", x_min=%s, x_max=%s, interpolant=%s, npoints=%s)'%(
                self._function, self._xmin, self._xmax, self._interpolant, self._npoints)

    def __eq__(self, other):
        if repr(self) != repr(other):
            return False
        return (self._rng.serialize() == other._rng.serialize() and
                self._function == other._function and
                self._xmin == other._xmin and
                self._xmax == other._xmax and
                self._interpolant == other._interpolant and
                self._npoints == other._npoints)

    # Functions aren't picklable, so for pickling, we reinitialize the DistDeviate using the
    # original function parameter, which may be a string or a file name.
    def __getinitargs__(self):
        return (self._rng.serialize(), self._function, self._xmin, self._xmax,
                self._interpolant, self._npoints)


def permute(rng, *args):
    """Randomly permute one or more lists.

    If more than one list is given, then all lists will have the same random permutation
    applied to it.

    @param rng    The random number generator to use. (This will be converted to a UniformDeviate.)
    @param args   Any number of lists to be permuted.
    """
    from .random import UniformDeviate
    ud = UniformDeviate(rng)
    if len(args) == 0:
        raise TypeError("permute called with no lists to permute")

    # We use an algorithm called the Knuth shuffle, which is based on the Fisher-Yates shuffle.
    # See http://en.wikipedia.org/wiki/Fisher-Yates_shuffle for more information.
    n = len(args[0])
    for i in range(n-1,1,-1):
        j = int((i+1) * ud())
        if j == i+1: j = i  # I'm not sure if this is possible, but just in case...
        for lst in args:
            lst[i], lst[j] = lst[j], lst[i]

# Some functions to enable pickling of deviates
_galsim.BaseDeviateImpl.__getinitargs__ = lambda self: (self.serialize(),)
_galsim.UniformDeviateImpl.__getinitargs__ = lambda self: (self.serialize(),)
_galsim.GaussianDeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.mean, self.sigma)
_galsim.BinomialDeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.n, self.p)
_galsim.PoissonDeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.mean)
_galsim.WeibullDeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.a, self.b)
_galsim.GammaDeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.k, self.theta)
_galsim.Chi2DeviateImpl.__getinitargs__ = lambda self: (self.serialize(), self.n)
