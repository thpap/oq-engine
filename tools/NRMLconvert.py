import sys
import time
from openquake.nrmllib.convert import (
    convert_nrml_to_zip, convert_zip_to_nrml, build_node)
from openquake.nrmllib.readers import FileReader


def collect(fnames):
    xmlfiles, zipfiles, csvmdatafiles, otherfiles = [], [],  [], []
    for fname in sorted(fnames):
        if fname.endswith('.xml'):
            xmlfiles.append(fname)
        elif fname.endswith('.zip'):
            zipfiles.append(fname)
        elif fname.endswith(('.csv', '.mdata')):
            csvmdatafiles.append(fname)
        else:
            otherfiles.append(fname)
    return xmlfiles, zipfiles, csvmdatafiles, otherfiles


def create(factory, fname):
    t0 = time.time()
    try:
        out = factory(fname)
    except Exception as e:
        print e
        return
    dt = time.time() - t0
    print 'Created %s in %s seconds' % (out, dt)


def main(*fnames):
    if not fnames:
        sys.exit('Please provide some input files')

    xmlfiles, zipfiles, csvmdatafiles, otherfiles = collect(fnames)
    for xmlfile in xmlfiles:
        create(convert_nrml_to_zip, xmlfile)

    for zipfile in zipfiles:
        create(convert_zip_to_nrml, zipfile)

    for name, group in FileReader.getall('.', csvmdatafiles):
        def convert_to_nrml(out):
            build_node(group, open(out, 'wb+'))
            return out
        create(convert_to_nrml, name + '.xml')

    if not xmlfiles and not zipfiles:
        sys.exit('Could not convert %s' % ' '.join(csvmdatafiles + otherfiles))


if __name__ == '__main__':
    main(*sys.argv[1:])
