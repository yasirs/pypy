import sys
from pypy.rlib import rstackovf

def recurse(n):
    if n > 0:
        return recurse(n-1) + n
    return 0

def f(n):
    try:
        recurse(n)
    except rstackovf.StackOverflow:
        return 1
    else:
        return 0


def test_direct():
    assert f(sys.maxint) == 1

def test_llinterp():
    from pypy.rpython.test.test_llinterp import interpret
    res = interpret(f, [sys.maxint])
    assert res == 1

def test_oointerp():
    from pypy.rpython.test.test_llinterp import interpret
    res = interpret(f, [sys.maxint], type_system='ootype')
    assert res == 1

def test_c_translation():
    from pypy.translator.c.test.test_genc import compile
    fn = compile(f, [int])
    res = fn(sys.maxint)
    assert res == 1