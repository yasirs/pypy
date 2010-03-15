from functools import partial

from pypy.objspace.flow import model as flowmodel
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.lltypesystem.lltype import Void
from pypy.translator.oosupport.function import Function as OOFunction
from pypy.translator.cli.node import Node
from pypy.translator.avm2 import types_ as types
from mech.fusion.avm2 import constants

class Function(OOFunction, Node):
    
    auto_propagate_exceptions = True

    def __init__(self, *args, **kwargs):
        OOFunction.__init__(self, *args, **kwargs)
        
        if hasattr(self.db.genoo, 'exceptiontransformer'):
            self.auto_propagate_exceptions = False
        
        namespace = getattr(self.graph.func, '_namespace_', None)
        if namespace:
            if '.' in namespace:
                self.namespace, self.classname = namespace.rsplit('.', 1)
            else:
                self.namespace = None
                self.classname = namespace
        else:
            self.namespace = None
            self.classname = None
        
        self.override = False
        
    def _create_generator(self, ilasm):
        ilasm.db = self.db
        return ilasm
    
    def record_ll_meta_exc(self, ll_meta_exc):
        # record the type only if it doesn't belong to a native_class
        ll_exc = ll_meta_exc._INSTANCE
        NATIVE_INSTANCE = ll_exc._hints.get('NATIVE_INSTANCE', None)
        if NATIVE_INSTANCE is None:
            OOFunction.record_ll_meta_exc(self, ll_meta_exc)

    def begin_render(self):
        self._set_args()
        self._set_locals()
        if not self.args:
            self.args = ()

        if self.is_method:
            self.args = self.args[1:]
        
        returntype, returnvar = self.cts.llvar_to_cts(self.graph.getreturnvar())

        if self.classname:
            self.generator.begin_class(constants.packagedQName(self.namespace, self.classname))
        
        self.generator.begin_method(self.name, self.args, returntype, static=not self.is_method, override=self.override)
        
    def end_render(self):
        # if self.generator.scope.islabel:
        #     self.generator.exit_scope()
        if self.classname:
            self.generator.exit_context()
        self.generator.exit_context()
        
    def render_return_block(self, block):
        return_var = block.inputargs[0]
        if return_var.concretetype is Void:
            self.generator.emit('returnvoid')
        else:
            self.generator.load(return_var)
            self.generator.emit('returnvalue')

    def set_label(self, label):
        return self.generator.set_label(label)

    def _trace_enabled(self):
        return True

    def _trace(self, s, writeline=False):
        print "TRACE:", s

    def _trace_value(self, prompt, v):
        print "TRACE: P:", prompt, "V:", v

    def _render_op(self, op):
        print "Rendering op:", op
        super(Function, self)._render_op(op)
    
    def _setup_link(self, link):
        target = link.target
        linkvars = []
        for to_load, to_store in zip(link.args, target.inputargs):
            if isinstance(to_load, flowmodel.Variable) and to_load.name == to_store.name:
                continue
            if to_load.concretetype is ootype.Void:
                continue
            linkvars.append((to_load, to_store))
        
        # after SSI_to_SSA it can happen to have to_load = [a, b] and
        # to_store = [b, c].  If we store each variable sequentially,
        # 'b' would be overwritten before being read.  To solve, we
        # first load all the values on the stack, then store in the
        # appropriate places.

        if self._trace_enabled():
            self._trace('link', writeline=True)
            for to_load, to_store in linkvars:
                self._trace_value('%s <-- %s' % (to_store, to_load), to_load)
            self._trace('', writeline=True)
        
        for to_load, to_store in linkvars:
            self.generator.load(to_load)
            self.generator.store(to_store)

    
    def begin_try(self, cond):
        if cond:
            self.ilasm.begin_try()
    
    def end_try(self, target_label, cond):
        if cond:
            self.ilasm.end_try()
        self.ilasm.branch_unconditionally(target_label)

    def begin_catch(self, llexitcase):
        ll_meta_exc = llexitcase
        ll_exc = ll_meta_exc._INSTANCE
        self.ilasm.begin_catch(ll_exc)

    def end_catch(self, target_label):
        self.ilasm.end_catch()
        self.ilasm.branch_unconditionally(target_label)

    def render_raise_block(self, block):
        exc = block.inputargs[1]
        self.generator.load(exc)
        self.generator.emit('throw')

    def store_exception_and_link(self, link):
        if self._is_raise_block(link.target):
            # the exception value is on the stack, use it as the 2nd target arg
            assert len(link.args) == 2
            assert len(link.target.inputargs) == 2
            self.store(link.target.inputargs[1])
        else:
            # the exception value is on the stack, store it in the proper place
            if isinstance(link.last_exception, flowmodel.Variable):
                self.ilasm.opcode('dup')
                self.store(link.last_exc_value)
                self.ilasm.emit('convert_o')
                self.ilasm.get_field('prototype')
                self.ilasm.get_field('constructor')
                self.store(link.last_exception)
            else:
                self.store(link.last_exc_value)
            self._setup_link(link)

    # def render_numeric_switch(self, block):
    #     if block.exitswitch.concretetype in (ootype.SignedLongLong, ootype.UnsignedLongLong):
    #         # TODO: it could be faster to check is the values fit in
    #         # 32bit, and perform a cast in that case
    #         self.render_numeric_switch_naive(block)
    #         return

    #     cases, min_case, max_case, default = self._collect_switch_cases(block)
    #     is_sparse = self._is_sparse_switch(cases, min_case, max_case)

    #     naive = (min_case < 0) or is_sparse
    #     if naive:
    #         self.render_numeric_switch_naive(block)
    #         return

    #     targets = []
    #     for i in xrange(max_case+1):
    #         link, lbl = cases.get(i, default)
    #         targets.append(lbl)
    #     self.generator.load(block.exitswitch)
    #     self.ilasm.switch(targets)
    #     self.render_switch_case(*default)
    #     for link, lbl in cases.itervalues():
    #         self.render_switch_case(link, lbl)

    # def call_oostring(self, ARGTYPE):
    #     if isinstance(ARGTYPE, ootype.Instance):
    #         argtype = self.cts.types.object
    #     else:
    #         argtype = self.cts.lltype_to_cts(ARGTYPE)
    #     self.call_signature('string [pypylib]pypy.runtime.Utils::OOString(%s, int32)' % argtype)

    # def call_oounicode(self, ARGTYPE):
    #     argtype = self.cts.lltype_to_cts(ARGTYPE)
    #     self.call_signature('string [pypylib]pypy.runtime.Utils::OOUnicode(%s)' % argtype)

    # Those parts of the generator interface that are function
    # specific