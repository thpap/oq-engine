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
import logging

from openquake.baselib import sap, parallel, config
from openquake.commonlib import oqvalidation, logs
from openquake.calculators import base
from openquake.server import dbserver

oqvalidation.OqParam.calculation_mode.validator.choices = tuple(
    base.calculators)
config.dbserver['receiver_ports'] = '1912-1940'


def run(job_ini, job1, job2):
    t0 = time.time()
    os.environ['OQ_DISTRIBUTE'] = 'no'
    os.environ['OQ_SAMPLE_SITES'] = '.0005'
    params = dict(calculation_mode='preclassical',
                  number_of_logic_tree_samples=10,
                  save_disk_space=True)
    with logs.handle(job1):
        base.get_calc(job_ini, job1, params).run()
    params['calculation_mode'] = 'event_based'
    with logs.handle(job2):
        base.get_calc(job_ini, job2, params).run()
    return dict(job_id=[job1, job2], dt=time.time() - t0)


@sap.script
def runmany(job_inis):
    """
    Run multiple calculations in parallel
    """
    t0 = time.time()
    dbserver.ensure_on()
    job_ids = [(logs.init('job'), logs.init('job')) for _ in job_inis]
    smap = parallel.Starmap(run)
    for job_ini, (job1, job2) in zip(job_inis, job_ids):
        smap.submit((job_ini, job1, job2))
    try:
        for dic in smap:
            logging.info('Finished %r' % dic)
    finally:
        parallel.Starmap.shutdown()
    logging.info('Finished in %d seconds' % (time.time() - t0))


runmany.arg('job_inis', 'calculation configuration file '
            '(or files, space-separated)', nargs='+')
