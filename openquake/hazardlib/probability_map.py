# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2016-2020 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import copy
from collections.abc import Mapping
import numpy

F32 = numpy.float32
F64 = numpy.float64


class AllEmptyProbabilityMaps(ValueError):
    """
    Raised by get_shape(pmaps) if all passed probability maps are empty
    """


class ProbabilityCurve(object):
    """
    This class is a small wrapper over an array of PoEs associated to
    a set of intensity measure types and levels. It provides a few operators,
    including the complement operator `~`

    ~p = 1 - p

    and the inclusive or operator `|`

    p = p1 | p2 = ~(~p1 * ~p2)

    Such operators are implemented efficiently at the numpy level, by
    dispatching on the underlying array.

    Here is an example of use:

    >>> poe = ProbabilityCurve(numpy.array([0.1, 0.2, 0.3, 0, 0]))
    >>> ~(poe | poe) * .5
    <ProbabilityCurve
    [0.405 0.32  0.245 0.5   0.5  ]>
    """
    def __init__(self, array):
        self.array = array

    def __or__(self, other):
        if other == 0:
            return self
        else:
            return self.__class__(1. - (1. - self.array) * (1. - other.array))
    __ror__ = __or__

    def __iadd__(self, other):
        # this is used when composing mutually exclusive probabilities
        self.array += other.array
        return self

    def __add__(self, other):
        # this is used when composing mutually exclusive probabilities
        self.array += other.array
        return self.__class__(self.array)

    def __mul__(self, other):
        if isinstance(other, self.__class__):
            return self.__class__(self.array * other.array)
        elif other == 1:
            return self
        else:
            return self.__class__(self.array * other)
    __rmul__ = __mul__

    def __pow__(self, n):
        return self.__class__(self.array ** n)

    def __invert__(self):
        return self.__class__(1. - self.array)

    def __bool__(self):
        return bool(self.array.any())

    def __repr__(self):
        return '<ProbabilityCurve\n%s>' % self.array

    # used when exporting to HDF5
    def convert(self, imtls, idx=0):
        """
        Convert a probability curve into a record of dtype `imtls.dt`.

        :param imtls: DictArray instance
        :param idx: extract the data corresponding to the given inner index
        """
        curve = numpy.zeros(1, imtls.dt)
        for imt in imtls:
            curve[imt] = self.array[imtls(imt), idx]
        return curve[0]


class ProbabilityMap(Mapping):
    """
    A dictionary site_id -> ProbabilityCurve. It defines the complement
    operator `~`, performing the complement on each curve

    ~p = 1 - p

    and the "inclusive or" operator `|`:

    m = m1 | m2 = {sid: m1[sid] | m2[sid] for sid in all_sids}

    Such operators are implemented efficiently at the numpy level, by
    dispatching on the underlying array. Moreover there is a classmethod
    .build(L, I, sids, initvalue) to build initialized instances of
    :class:`ProbabilityMap`. The map can be represented as a 3D array of shape
    (shape_x, shape_y, shape_z) = (N, L, G), where N is the number of site IDs,
    L the total number of hazard levels and G the number of GSIMs.
    """
    @classmethod
    def build(cls, shape_y, shape_z, sids, initvalue=0., dtype=F64):
        """
        :param shape_y: the total number of intensity measure levels
        :param shape_z: the number of inner levels
        :param sids: a set of site indices
        :param initvalue: the initial value of the probability (default 0)
        :returns: a ProbabilityMap dictionary
        """
        self = cls(numpy.uint32(sorted(set(sids))), shape_y, shape_z)
        self.array[:] = initvalue
        return self

    @classmethod
    def from_array(cls, array, sids):
        """
        :param array: array of shape (N, L) or (N, L, I)
        :param sids: array of N sorted site IDs
        """
        n_sites = len(sids)
        n = len(array)
        if n_sites != n:
            raise ValueError('Passed %d site IDs, but the array has length %d'
                             % (n_sites, n))
        if len(array.shape) == 2:  # shape (N, L) -> (N, L, 1)
            array = array.reshape(array.shape + (1,))
        self = cls(sids, *array.shape[1:])
        self.array = array
        return self

    def __init__(self, sids, shape_y, shape_z=1):
        self.sids = sids
        self.sidx = {sid: idx for idx, sid in enumerate(sids)}
        self.shape_y = shape_y
        self.shape_z = shape_z
        self.array = numpy.zeros((len(sids), shape_y, shape_z))

    # used when exporting to HDF5
    def convert(self, imtls, nsites, idx=0):
        """
        Convert a probability map into a composite array of length `nsites`
        and dtype `imtls.dt`.

        :param imtls:
            DictArray instance
        :param nsites:
            the total number of sites
        :param idx:
            index on the z-axis (default 0)
        """
        curves = numpy.zeros(nsites, imtls.dt)
        for imt in curves.dtype.names:
            curves_by_imt = curves[imt]
            for sid in self:
                curves_by_imt[sid] = self[sid][imtls(imt), idx]
        return curves

    def copy(self):
        """
        :returns: an independent copy of the ProbabilityMap
        """
        new = copy.copy(self)
        new.array = numpy.array(self.array)
        return new

    def filter(self, sids):
        """
        Extracs a submap of self for the given sids.
        """
        new = self.copy()
        for sid in sids:
            new[sid] = self[sid]
        return new

    def extract(self, inner_idx):
        """
        Extracts a component of the underlying ProbabilityCurves,
        specified by the index `inner_idx`.
        """
        out = self.__class__(self.sids, self.shape_y, 1)
        for sid in self:
            out[sid] = self[sid][:, inner_idx].reshape(-1, 1)  # shape (L, 1)
        return out

    def __ior__(self, other):
        if not other:
            return self
        if (other.shape_y, other.shape_z) != (self.shape_y, self.shape_z):
            raise ValueError('%s has inconsistent shape with %s' %
                             (other, self))
        for sid in other.sids:
            self[sid] += other[sid] - self[sid] * other[sid]
        return self

    def __or__(self, other):
        new = self.copy()
        new |= other
        return new

    __ror__ = __or__

    def __add__(self, other):
        new = self.copy()
        if hasattr(other, 'sids'):  # assume it is a pmap
            for sid in other:
                new[sid] += other[sid]
        else:  # assume it is a float
            assert 0. <= other <= 1., other  # must be a probability
            new.array += other
        return new

    def __iadd__(self, other):
        # this is used when composing mutually exclusive probabilities
        for sid in other:
            self[sid] += other[sid]
        return self

    def __mul__(self, other):
        new = self.copy()
        if hasattr(other, 'sids'):  # assume it is a pmap
            for sid in other:
                new[sid] *= other[sid]
        else:  # assume it is a float
            new.array *= other
        return new

    def __pow__(self, n):
        new = self.__class__.__new__(self.__class__)
        vars(new).update(vars(self))
        new.array = self.array ** n
        return new

    _ipow__ = __pow__

    def __invert__(self):
        new = self.__class__.__new__(self.__class__)
        vars(new).update(vars(self))
        new.array = 1. - self.array
        return new

    def __getitem__(self, sid):
        return self.array[self.sidx[sid]]

    def __setitem__(self, sid, arr):
        self.array[self.sidx[sid]] = arr

    def __iter__(self):
        yield from self.sids

    def __len__(self):
        return len(self.sids)

    def __toh5__(self):
        return dict(array=self.array, sids=self.sids), {}

    def __fromh5__(self, dic, attrs):
        self.array = dic['array']
        self.sids = dic['sids']
        self.sidx = {sid: idx for idx, sid in enumerate(self.sids)}
        self.shape_y = self.array.shape[1]
        self.shape_z = self.array.shape[2]

    def __repr__(self):
        return '<%s %d, %d, %d>' % (self.__class__.__name__, len(self),
                                    self.shape_y, self.shape_z)


def get_shape(pmaps):
    """
    :param pmaps: a set of homogenous ProbabilityMaps
    :returns: the common shape (N, L, I)
    """
    for pmap in pmaps:
        if pmap:
            sid = next(iter(pmap))
            break
    else:
        raise AllEmptyProbabilityMaps(pmaps)
    return (len(pmap),) + pmap[sid].array.shape


def combine(pmaps):
    """
    :param pmaps: a set of homogenous ProbabilityMaps
    :returns: the combined map
    """
    shape = get_shape(pmaps)
    res = ProbabilityMap(shape[1], shape[2])
    for pmap in pmaps:
        res |= pmap
    return res
