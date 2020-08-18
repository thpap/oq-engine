Logic tree sampling strategies
==============================

Logic tree sampling is controlled by the following three parameters in the
``job.ini``:

- number_of_logic_tree_samples (default 0, no sampling)
- sampling_method (default ``early_weights``)
- random_seed (default 42)

Stating from version 3.10, the OpenQuake engine supports 4 different
sampling methods. They are called, respectively, ``early_weights``,
``late_weights``, ``early_latin``, ``late_latin``.  Here we will
discuss how they work by considering an example with two source models
with weights 0.4 and 0.6 respectively (branches ``sm1`` and ``sm2``)
and one tectonic region type with three GSIMs with weights 0.2, 0.3
and 0.5 respectively (branches `g1``, ``g2`` and ``g3``). For the sake
of the example, we will consider ``number_of_logic_tree_samples=100``
and ``random_seed=42``.

*early_weights*

In this case the engine will use the weights to choose which branch
to take in the source model logic tree by calling a function called
``random_choice(weights, size, seed)`` in hazardlib, returning branch
indices::

>>> from openquake.hazardlib.lt import random_choice
>>> sm_indices = random_choice([0.4, 0.6], size=100, seed=42)
>>> sm_indices
array([0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0,
       0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1,
       0, 1, 0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1,
       0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1,
       1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0])

Since ``number_of_logic_tree_samples=100`` the size of the returned array
will be 100; the array will contains zeros (corresponding to the branch
``sm1``) or ones (corresponding to the branch ``sm2``). If you count the
number of zeros you should to have around 40 of them, since the weight
of the ``sm1`` branch is 0.4; if you count the
number of ones you should to have around 60 of them, since the weight
of the ``sm2`` branch is 0.6; in practice, with out choice of the seed
we have

>>> import numpy
>>> numpy.bincount(sm_indices)                                              
array([46, 54])

Now the engine has to perform the gsim logic tree sampling:

>>> sm_indices = random_choice([0.2, 0.3, 0.5], size=100, seed=42)
>>> sm_indices

