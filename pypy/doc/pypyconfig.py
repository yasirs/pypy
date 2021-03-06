

def setup(app):
    import sys, os
    sys.path.insert(0, os.path.abspath("../../"))
    from pypy.config import makerestdoc
    import py
    role = makerestdoc.register_config_role(py.path.local())
    app.add_role("config", role)
