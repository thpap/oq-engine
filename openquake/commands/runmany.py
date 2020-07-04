# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2020 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.
import os.path
import time
import numpy

from openquake.baselib import sap, parallel, config
from openquake.commonlib import oqvalidation, logs
from openquake.calculators import base
from openquake.server import dbserver

oqvalidation.OqParam.calculation_mode.validator.choices = tuple(
    base.calculators)
config.dbserver['receiver_ports'] = '1912-1940'


def run(job_ini, calc_id):
    t0 = time.time()
    print('Running %s #%d' % (job_ini, calc_id))
    os.environ['OQ_DISTRIBUTE'] = 'no'
    os.environ['OQ_SAMPLE_SITES'] = '.0005'
    params = dict(calculation_mode='preclassical',
                  number_of_logic_tree_samples=10,
                  save_disk_space=True)
    base.get_calc(job_ini, calc_id, params).run()
    params['calculation_mode'] = 'event_based'
    base.get_calc(job_ini, calc_id + 1, params).run()
    return dict(calc_id=[calc_id, calc_id + 1], dt=time.time() - t0)


@sap.script
def runmany(job_inis):
    """
    Run multiple calculations in parallel
    """
    dbserver.ensure_on()
    calc_id = logs.init()
    calc_ids = calc_id + 1 + numpy.arange(0, len(job_inis) * 2, 2)
    print('Running %s' % calc_ids)
    smap = parallel.Starmap(run)
    t0 = time.time()
    for job_ini, calc_id in zip(job_inis, calc_ids):
        smap.submit((job_ini, calc_id))
    try:
        for dic in smap:
            print(dic)
    finally:
        parallel.Starmap.shutdown()
    print('Finished in %d seconds' % (time.time() - t0))


runmany.arg('job_inis', 'calculation configuration file '
            '(or files, space-separated)', nargs='+')
