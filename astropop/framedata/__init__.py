# Licensed under a 3-clause BSD style license - see LICENSE.rst

from .framedata import FrameData, setup_filename, framedata_read_fits, framedata_to_hdu, extract_units  # noqa
from .memmap import MemMapArray, create_array_memmap, delete_array_memmap  # noqa
from .utils import check_framedata  # noqa
from .compat import imhdus, EmptyDataError  # noqa