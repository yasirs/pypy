# this script is used for extracting
# the information available for exceptions
# via introspection.
# The idea is to use it once to create
# a template for a re-birth of exceptions.py

import types

def classOfAttribute(klass, attname):
    if attname in klass.__dict__:
        return klass
    for base in klass.__bases__:
        ret = classOfAttribute(base, attname)
        if ret:
            return ret

def getAttributes(klass, ignorelist = []):
    return [name for name in dir(klass) if name not in ignorelist]

def makeExceptionsTemplate(f=None):
    
    def enumExceptionsInOrder():
        import exceptions
        seen = {}
        ordered = []
        
        def enumerateOne(exc):
            seen[exc] = 1
            for each in exc.__bases__:
                if each not in seen:
                    enumerateOne(each)
            ordered.append(exc)
            
        for each in exceptions.__dict__.values():
            if isinstance(each, (types.ClassType, type)) and \
               each not in seen:
                enumerateOne(each)

        return ordered

    if not f:
        f = sys.stdout

    for exc in enumExceptionsInOrder():
        name = exc.__name__
        bases = exc.__bases__
        doc = exc.__doc__
        bases = [this.__name__ for this in bases]
        bases = ", ".join(bases)
        if bases: bases = "(%s)" % bases

        ignorelist = "__doc__ __module__".split()
        # find out class variables and methods
        simple = []
        difficult = []
        for attname in getAttributes(exc, ignorelist):
            if classOfAttribute(exc, attname) is exc:
                obj = getattr(exc, attname)
                (simple, difficult)[callable(obj)].append( (attname, obj) )
        print >> f, "class %s%s:" % (name, bases)
        if doc:
            print >> f, '    """%s"""' % doc
        if not (simple or difficult or doc):
            print >> f, "    pass"
        for tup in simple:
            print >> f, "    %s = %r" % tup

        for attname, meth in difficult:
            print >> f
            func = globals().get("tryGenerate" + attname, None)
            if not func:
                print >> f, "    # please implement %s.%s (%r)" % (name, attname, meth)
            else:
                try:
                    print >> f, "    # auto-generated code, please check carefully!"
                    for line in func(exc):
                        print >> f, "    " + line
                except ValueError, e:
                    print >> f, "    # %s" % e
                    print >> f, "    # please implement %s.%s (%r)" % (name, attname, meth)
        print >> f

def tryGenerate__getitem__(exc):
    for args in (), (1, 2, 3):
        try:
            sample = exc(*args)
        except:
            raise ValueError, "cannot create instance"
        if "args" not in sample.__dict__:
            raise ValueError, "args attribute not found in __dict__"
        if args != sample.args:
            raise ValueError, "instance has modified args"
        for i in range(5):
            try: x = sample[i]
            except IndexError: x = 42
            try: y = args[i]
            except IndexError: y = 42
            if x != y:
                raise ValueError, "args does not behave like a sequence"
    del sample.args
    try: x = sample[0]
    except: x = 42
    use_default = x is None
    # looks fine so far.
    yield "def __getitem__(self, idx):"
    if use_default:
        yield "    if not hasattr(self, 'args'):"
        yield "        return None"
    yield "    return self.args[idx]"


class ProbeObject(object):
    """ this class creates general "any" objects, and
        for the special case of SyntaxError, it can behave
        like a subscriptable object
    """
    def __init__(self, argpos, maxprobe=None):
        self.argpos = argpos
        self.maxprobe = maxprobe
        self.probed = []
    def __getitem__(self, idx):
        if idx not in self.probed:
            self.probed.append(idx)
        if self.maxprobe is not None and idx > self.maxprobe:
            raise IndexError, "cheat cheat %d" % idx
        return "arg%d_%s" % (self.argpos, idx)
    def __repr__(self):
        if self.probed:
            return "<arg%d:%r>" % (self.argpos, self.probed)
        else:
            return "<arg%d>" % self.argpos
    def __str__(self):
        # make this different from repr!
        return repr(self)[1:-1]
    def __cmp__(self, other):
        return cmp( (self.argpos, self.probed), other)

def genArgsToTry(argpos):
    args = [ProbeObject(argpos),
            "arg%d" % argpos, u"arg%d" %argpos, 1000+argpos*10]
    return args

def cartesian(*args):
    if len(args)== 0:
        yield args
    elif len(args) == 1:
        for item in args[0]:
            yield (item,)
    else:
        for item in args[0]:
            for other in cartesian(*args[1:]):
                yield (item,) + other

def probeArgCount(exc, maxprobe=20):
    worksmaybe = []
    for i in range(maxprobe):
        try:
            probe = exc(*(i,)*i) # test i-tuple
            worksmaybe.append(i)
        except TypeError, e:
            if not str(e).startswith("function takes "):
                worksmaybe.append(i)
        except:
            pass
    return min(worksmaybe), max(worksmaybe)

def refreshArgs(tup):
    res = []
    for arg in tup:
        if type(arg) is ProbeObject:
            arg = ProbeObject(arg.argpos) # cleanup probing
        res.append(arg)
    return tuple(res)

def findAllArgs(exc, maxprobe):
    minargs, maxargs = probeArgCount(exc, maxprobe=20)
    res = []
    # for minargs args, we need to try combinations
    arglist = tuple([genArgsToTry(i) for i in range(minargs)])
    for args in cartesian(*arglist):
        try:
            probe = exc(*args)
            res.append(args)
            works = refreshArgs(args)
            break
        except Exception, e:
            continue
    else:
        raise TypeError, "cannot analyse arguments of %s" % exc.__name__
    # for the variable part, don't try combinations
    for i in range(minargs, maxargs):
        for arg in genArgsToTry(i):
            args = works + (arg,)
            try:
                probe = exc(*args)
                res.append(args)
                works = refreshArgs(args)
                break
            except:
                continue
        else:
            raise TypeError, "cannot analyse arguments of %s" % exc.__name__
    return minargs, maxargs, res

def captureAssignments(exc, args):
    """ we wrap a class around the exc class and record attribute access """
    assigned = []
    class WrapExc(exc):
        def __setattr__(self, name, obj):
            assigned.append( (name, obj) )
            self.__dict__[name] = obj
    probe = WrapExc(*args)
    names = {}
    names[args] = "args"
    for i, arg in enumerate(args):
        names[arg] = "args[%d]" % i
        if not isinstance(arg, ProbeObject):
            continue
        for subidx in arg.probed:
            names[arg[subidx]] = "args[%d][%d]" % (i, subidx)
    def nameof(obj):
        if obj in names:
            return names[obj]
        elif isinstance(obj, (tuple, list)):
            stuff = [nameof(x) for x in obj]
            br = str(type(obj)())
            txt = br[0] + ", ".join(stuff) + br[-1]
            names[obj] = txt
        else:
            names[obj] = "%r # default, hopefully" % obj
        return names[obj]
    res = []
    for name, obj in assigned:
        res.append("self.%s = %s" % (name, nameof(obj)))
    return tuple(res)

def tryGenerate__init__(exc, maxprobe=20):
    minargs, maxargs, working = findAllArgs(exc, maxprobe)
    # merge assignments in order, record set of arg counts
    foldcases = {}
    for args in working:
        singleprog = captureAssignments(exc, args)
        for tup in enumerate(singleprog):
            foldcases.setdefault(tup, [])
            foldcases[tup].append(len(args))
    # group assignments by set of arg counts and order
    groupassign = {}
    for (order, assignment), argcounts in foldcases.items():
        key = tuple(argcounts)
        # special case: we don't raise errors
        # and always assign to self.args
        if assignment == "self.args = args" and len(key) != maxprobe:
            assignment += " # modified: always assign args, no error check"
            key = tuple(range(maxprobe))
        groupassign.setdefault(key, [])
        groupassign[key].append( (order, assignment) )
    cases = groupassign.items()
    cases.sort()
    yield "def __init__(self, *args):"
    if len(cases) > 1 or len(cases[0][0]) != maxprobe:
        yield "    argc = len(args)"
    for argcounts, ordered_statements in cases:
        ordered_statements.sort()
        if len(argcounts) == maxprobe:
            # all counts, no condition
            indent = 1
        else:
            indent = 2
            dense = tuple(range(argcounts[0], argcounts[-1]+1)) == argcounts
            if len(argcounts) == 1:
                yield "    if argc == %d:" % argcounts
            elif dense and argcounts[0] == 0:
                yield "    if argc <= %d:" % argcounts[-1]
            elif dense and argcounts[-1] == maxprobe-1:
                yield "    if argc >= %d:" % argcounts[0]
            elif dense:
                yield "    if %d <= argc <= %d:" % (argcounts[0], argcounts[-1])
            else:
                yield "    if argc in %r:" % (argcounts, )
        for order, line in ordered_statements:
            yield indent * "    " + line

def tryGenerate__str__(exc, maxprobe=20):
    minargs, maxargs, working = findAllArgs(exc, maxprobe)
    # checking the default case (well, there are two)
    simple = False
    arg1_methods = []
    for args in working:
        test = str(exc(*args))
        if len(args) == 0 and test != "":
            break
        if len(args) == 1:
            if test == repr(args[0]):
                arg1_methods.append("repr")
            elif test == str(args[0]):
                arg1_methods.append("str")
            else:
                break
        if len(args) >= 2 and test != repr(args):
            break
    else:
        simple = arg1_methods and min(arg1_methods) == max(arg1_methods)
    if simple:
        yield "def __str__(self):"
        yield "    argc = len(self.args)"
        yield "    if argc == 0:"
        yield "        return ''"
        yield "    elif argc == 1:"
        yield "        return %s(self.args[0])" % arg1_methods.pop()
        yield "    else:"
        yield "        return str(self.args)"
        return
    # no idea how I should do this
    probe = exc(*working[0])
    dic = probe.__dict__
    for key in dic.keys():
        if key.startswith("__") and key.endswith("__"):
            del dic[key]
    yield "def __str__(self):"
    yield "    # this is a bad hack, please supply an implementation"
    yield "    res = ' '.join(["
    for key in dic.keys():
        yield "       '%s=' + str(self.%s)," % (key, key)
    yield "    ])"
    yield "    return res"

if __name__ == "__main__":
    import pypy.appspace, os
    targetdir = os.path.dirname(pypy.appspace.__file__)
    fname = os.path.join(targetdir, "_exceptions.py")
    makeExceptionsTemplate(file(fname, "w"))
