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
import logging
import os.path
import time

from openquake.baselib import performance, sap, parallel, config
from openquake.commonlib import oqvalidation, logs
from openquake.calculators import base
from openquake.server import dbserver

oqvalidation.OqParam.calculation_mode.validator.choices = tuple(
    base.calculators)
config.dbserver['receiver_ports'] = '1912-1940'


def run(job_ini, calc_id, params, monitor=performance.Monitor()):
    print('Running %s #%d' % (job_ini, calc_id))
    os.environ['OQ_DISTRIBUTE'] = 'no'
    os.environ['OQ_SAMPLE_SITES'] = '.0005'
    # set the logs first of all
    # disable gzip_input
    base.BaseCalculator.gzip_inputs = lambda self: None
    base.get_calc(job_ini, calc_id).run(**params)
    return {}


PARAM = ('calculation_mode=preclassical,number_of_logic_tree_samples=10,'
         'save_disk_space=1')


@sap.script
def runmany(job_inis, param=PARAM):
    """
    Run multiple calculations bypassing the database layer
    """
    dbserver.ensure_on()
    if param:
        params = oqvalidation.OqParam.check(
            dict(p.split('=', 1) for p in param.split(',')))
    else:
        params = {}
    calc_ids = [logs.init('job', logging.WARN) for _ in job_inis]
    smap = parallel.Starmap(run)
    t0 = time.time()
    for job_ini, calc_id in zip(job_inis, calc_ids):
        smap.submit((job_ini, calc_id, params))
    try:
        smap.reduce()
    finally:
        parallel.Starmap.shutdown()
    print('Finished in %d seconds' % (time.time() - t0))


runmany.arg('job_inis', 'calculation configuration file '
            '(or files, space-separated)', nargs='+')
runmany.arg('param', 'parameters in TOML format')
