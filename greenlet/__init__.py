# For external projects that want a "svn:externals" link
# to greenlets, please use the following svn:externals:
#
#     greenlet http://codespeak.net/svn/greenlet/trunk/c
#
# This file is here to have such a case work transparently
# with auto-compilation of the .c file.  It requires the
# py lib, however. (the need could be factored out though)

import sys
if '__pypy__' in sys.builtin_module_names:
    # On top of PyPy, we fish 'greenlet' from the '_stackless'
    # module, which is available in pypy-c-stackless versions.
    # Other versions of PyPy are not supported.
    from _stackless import greenlet
else:
    # On top of CPython, build and use '_greenlet.c'.
    from greenlet.buildcmodule import make_module_from_c
    import py as _py
    _path = _py.path.local(__file__).dirpath().join('_greenlet.c')
    _module = make_module_from_c(_path)
    globals().update(_module.__dict__)
