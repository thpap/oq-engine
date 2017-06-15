#  -*- coding: utf-8 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2017, GEM Foundation

#  OpenQuake is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  OpenQuake is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.

#  You should have received a copy of the GNU Affero General Public License
#  along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.
import time
import shutil
import sqlite3
import os.path
import tempfile
from openquake.baselib import sap
from openquake.baselib.general import safeprint
from openquake.server.manage import db
from openquake.engine.export.core import zipfiles


def smart_save(dbpath, archive):
    """
    Make a copy of the db, remove the incomplete jobs and add the copy
    to the archive
    """
    tmpdir = tempfile.mkdtemp()
    newdb = os.path.join(tmpdir, os.path.basename(dbpath))
    shutil.copy(dbpath, newdb)
    try:
        with sqlite3.connect(newdb) as conn:
            conn.execute('DELETE FROM job WHERE status != "complete"')
    except:
        safeprint('Please check the copy of the db in %s' % newdb)
        raise
    zipfiles([newdb], archive, 'a', safeprint)
    shutil.rmtree(tmpdir)


@sap.Script
def dump(archive, user=None):
    """
    Dump the openquake database and all the complete calculations into a zip
    file. In a multiuser installation must be run as administrator.
    """
    t0 = time.time()
    assert archive.endswith('.zip'), archive
    getfnames = 'select ds_calc_dir || ".hdf5" from job where ?A'
    param = dict(status='complete')
    if user:
        param['user_name'] = user
    fnames = [f for f, in db(getfnames, param) if os.path.exists(f)]
    zipfiles(fnames, archive, 'w', safeprint)
    pending_jobs = db('select id, status, description from job '
                      'where status="executing"')
    if pending_jobs:
        safeprint('WARNING: there were calculations executing during the dump,'
                  ' they have been not copied')
        for job_id, status, descr in pending_jobs:
            safeprint('%d %s %s' % (job_id, status, descr))
        # this also checks that the copied db is not corrupted
        smart_save(db.path, archive)
    else:
        zipfiles([db.path], archive, 'a', safeprint)

    dt = time.time() - t0
    safeprint('Archived %d files into %s in %d seconds'
              % (len(fnames) + 1, archive, dt))


dump.arg('archive', 'path to the zip file where to dump the calculations')
dump.arg('user', 'if missing, dump all calculations')
