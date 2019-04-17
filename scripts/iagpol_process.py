#!/bin/env python3

import os
import datetime
from optparse import OptionParser

from astropop.pipelines.automatic.opd import BCCalib, IAGPOLPipeline
from astropop.catalogs import ASCIICatalogClass
from astropop.py_utils import mkdir_p
from astropop.logger import logger

def main():
    parser = OptionParser("usage: %prog [options] raw_dir [raw_dir2, ...]")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="count",
                      help="Enable 'DEBUG' output in python log")
    parser.add_option("-a", "--astrometry", dest="astrometry",
                      action="store_true",
                      default=False,
                      help="Enable astrometry solving of stacked images "
                           "with astrometry.net")
    parser.add_option("-n", "--science-catalog", dest="science_catalog",
                      default=None, metavar="FILE",
                      help="ASCII catalog to identify science stars. "
                           "Has to be astropy's table readable with columns "
                           "ID, RA, DEC")
    parser.add_option("-l", "--save-log", dest="save_log",
                      default=None, metavar="FILE",
                      help="Save log to FILE. If '%date' value, automatic name"
                           " based on date will be created.")
    parser.add_option("-d", "--dest", dest="reduced_folder",
                      default='~/astropop_reduced', metavar="FOLDER",
                      help="Reduced images (and created calib frames) will "
                           "be saved at inside FOLDER")
    parser.add_option("-c", "--calib", dest="calib_folder",
                      default=None, metavar="FOLDER",
                      help="Load/save calibration frames from/in FOLDER. "
                           "If not set, reduced_folder/calib will be used"
                           " instead.")

    (options, args) = parser.parse_args()

    if len(args) < 1:
        raise ValueError('No raw folder passed!')

    raw_dirs = args

    if options.verbose is None:
        logger.setLevel('WARN')
    elif options.verbose == 1:
        logger.setLevel('INFO')
    else:
        logger.setLevel('DEBUG')

    astrometry = options.astrometry
    reduced_folder = os.path.expanduser(options.reduced_folder)
    reduced_folder = os.path.abspath(reduced_folder)
    mkdir_p(reduced_folder)

    if options.calib_folder is not None:
        calib_folder = os.path.expanduser(options.calib_folder)
        calib_folder = os.path.abspath(calib_folder)
    else:
        calib_folder = os.path.join(reduced_folder, 'calib')

    sci_cat = options.science_catalog
    if sci_cat is not None:
        sci_cat = ASCIICatalogClass(sci_cat, id_key='ID', ra_key='RA',
                                    dec_key='DEC', format='ascii')

    mkdir_p(reduced_folder)

    def _process():
        for fold in raw_dirs:
            pipe = BCCalib(product_dir=reduced_folder,
                           calib_dir=calib_folder,
                           ext=0, fits_extensions=['.fits'],
                           compression=True)
            pipe_phot = IAGPOLPipeline(product_dir=reduced_folder,
                                       image_ext=1)
            prods = pipe.run(fold, astrometry=astrometry, stack_images=False,
                             save_calibed=True)
            pipe_phot.process_products(prods, sci_cat)
            del pipe
            del pipe_phot

    if options.save_log is not None:
        name = options.save_log
        if name == '%date':
            d = datetime.datetime.now()
            d = d.isoformat(timespec='seconds')
            name = "astropop_{}.log".format(d)
            name = os.path.join(reduced_folder, name)
        with logger.log_to_file(name):
            _process()
    else:
        _process()

if __name__ == '__main__':
    main()