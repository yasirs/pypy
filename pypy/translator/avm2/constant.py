
from pypy.translator.oosupport.constant import \
     push_constant, WeakRefConst, StaticMethodConst, CustomDictConst, \
     ListConst, ClassConst, InstanceConst, RecordConst, DictConst, \
     BaseConstantGenerator, AbstractConst, ArrayConst
from pypy.rpython.ootypesystem import ootype
from pypy.translator.avm2 import types_ as types
from pypy.rpython.lltypesystem import lltype

from mech.fusion.avm2 import constants, traits

CONST_CLASS = constants.packagedQName("pypy.runtime", "Constants")

# ______________________________________________________________________
# Constant Generators
#
# Different generators implementing different techniques for loading
# constants (Static fields, singleton fields, etc)

class Avm2ConstGenerator(BaseConstantGenerator):

    def __init__(self, db):
        BaseConstantGenerator.__init__(self, db)
        self.cts = db.genoo.TypeSystem(db)

    def _begin_gen_constants(self, gen, all_constants):
        self.ilasm = gen
        self.begin_class()
        return gen

    def _end_gen_constants(self, gen, numsteps):
        assert gen is self.ilasm
        self.end_class()

    def begin_class(self):
        self.ctx = self.ilasm.begin_class(CONST_CLASS)
        self.ctx.make_cinit()

    def end_class(self):
        self.ilasm.exit_context()
        self.ilasm.exit_context()
    
    def _declare_const(self, gen, const):
        self.ctx.add_static_trait(traits.AbcConstTrait(constants.QName(const.name), const.get_type().multiname()))

    def downcast_constant(self, gen, const, EXPECTED_TYPE):
        type = self.cts.lltype_to_cts(EXPECTED_TYPE)
        gen.emit('coerce', type.multiname())
 
    def _get_key_for_const(self, value):
        if isinstance(value, ootype._view) and isinstance(value._inst, ootype._record):
            return value._inst
        return BaseConstantGenerator._get_key_for_const(self, value)
    
    def push_constant(self, gen, const):
        gen.emit('getlex', CONST_CLASS)
        gen.emit('getproperty', constants.QName(const.name))

    def _push_constant_during_init(self, gen, const):
        gen.push_this()
        gen.emit('getproperty', constants.QName(const.name))

    def _pre_store_constant(self, gen, const):
        gen.push_this()
    
    def _store_constant(self, gen, const):
        gen.emit('initproperty', constants.QName(const.name))

    def _initialize_data(self, gen, all_constants):
        """ Iterates through each constant, initializing its data. """
        for const in all_constants:
            self._consider_step(gen)
            self._push_constant_during_init(gen, const)
            self.current_const = const
            if not const.initialize_data(self, gen):
                gen.pop()

    def _declare_step(self, gen, stepnum):
        pass

    def _close_step(self, gen, stepnum):
        pass

    # def _create_complex_const(self, value):
        # if isinstance(value, _fieldinfo):
        #     uniq = self.db.unique()
        #     return CLIFieldInfoConst(self.db, value.llvalue, uniq)
        # elif isinstance(value, ootype._view) and isinstance(value._inst, ootype._record):
        #     self.db.cts.lltype_to_cts(value._inst._TYPE) # record the type of the record
        #     return self.record_const(value._inst)
        # else:
        #     return BaseConstantGenerator._create_complex_const(self, value)


# ______________________________________________________________________
# Mixins
#
# Mixins are used to add a few Tamarin-specific methods to each constant
# class.  Basically, any time I wanted to extend a base class (such as
# AbstractConst or DictConst), I created a mixin, and then mixed it in
# to each sub-class of that base-class.  Kind of awkward.

class Avm2BaseConstMixin(object):
    """ A mix-in with a few extra methods the Tamarin backend uses """
    
    def get_type(self):
        """ Returns the Tamrin type for this constant's representation """
        return self.cts.lltype_to_cts(self.value._TYPE)
    
    def push_inline(self, gen, TYPE):
        """ Overload the oosupport version so that we use the Tamarin
        opcode for pushing NULL """
        assert self.is_null()
        gen.ilasm.push_null()

# class Avm2DictMixin(Avm2BaseConstMixin):
#     def _check_for_void_dict(self, gen):
#         KEYTYPE = self.value._TYPE._KEYTYPE
#         keytype = self.cts.lltype_to_cts(KEYTYPE)
#         keytype_T = self.cts.lltype_to_cts(self.value._TYPE.KEYTYPE_T)
#         VALUETYPE = self.value._TYPE._VALUETYPE
#         valuetype = self.cts.lltype_to_cts(VALUETYPE)
#         valuetype_T = self.cts.lltype_to_cts(self.value._TYPE.VALUETYPE_T)
#         if VALUETYPE is ootype.Void:
#             gen.add_comment('  CLI Dictionary w/ void value')
#             class_name = PYPY_DICT_OF_VOID % keytype
#             for key in self.value._dict:
#                 gen.ilasm.opcode('dup')
#                 push_constant(self.db, KEYTYPE, key, gen)
#                 meth = 'void class %s::ll_set(%s)' % (class_name, keytype_T)
#                 gen.ilasm.call_method(meth, False)
#             return True
#         return False
    
#     def initialize_data(self, constgen, gen):
#         # special case: dict of void, ignore the values
#         if self._check_for_void_dict(gen):
#             return 
#         return super(Avm2DictMixin, self).initialize_data(constgen, gen)

# ______________________________________________________________________
# Constant Classes
#
# Here we overload a few methods, and mix in the base classes above.
# Note that the mix-ins go first so that they overload methods where
# required.
#
# Eventually, these probably wouldn't need to exist at all (the JVM
# doesn't have any, for example), or could simply have empty bodies
# and exist to combine a mixin and the generic base class.  For now,
# though, they contain the create_pointer() and initialize_data()
# routines.  In order to get rid of them, we would need to implement
# the generator interface in Tamarin.

class Avm2RecordConst(Avm2BaseConstMixin, RecordConst):
    def create_pointer(self, gen):
        self.db.const_count.inc('Record')
        super(Avm2RecordConst, self).create_pointer(gen)

    def initialize_data(self, constgen, gen):
        assert not self.is_null()
        SELFTYPE = self.value._TYPE
        for f_name, (FIELD_TYPE, f_default) in self.value._TYPE._fields.iteritems():
            if FIELD_TYPE is not ootype.Void:
                gen.dup()
                value = self.value._items[f_name]
                push_constant(self.db, FIELD_TYPE, value, gen)
                gen.set_field(f_name)

class Avm2InstanceConst(Avm2BaseConstMixin, InstanceConst):
    def create_pointer(self, gen):
        self.db.const_count.inc('Instance')
        self.db.const_count.inc('Instance', self.OOTYPE())
        super(Avm2InstanceConst, self).create_pointer(gen)

    def initialize_data(self, constgen, gen):
        assert not self.is_null()

        # Get a list of all the constants we'll need to initialize.
        # I am not clear on why this needs to be sorted, actually,
        # but we sort it.
        const_list = self._sorted_const_list()
        
        # Push ourself on the stack, and cast to our actual type if it
        # is not the same as our static type
        SELFTYPE = self.value._TYPE
        if SELFTYPE is not self.static_type:
            gen.downcast(SELFTYPE)

        # Store each of our fields in the sorted order
        for FIELD_TYPE, INSTANCE, name, value in const_list:
            constgen._consider_split_current_function(gen)
            gen.dup()
            push_constant(self.db, FIELD_TYPE, value, gen)
            gen.set_field(name)

class Avm2ClassConst(Avm2BaseConstMixin, ClassConst):
    def is_inline(self):
        return True

    def push_inline(self, gen, EXPECTED_TYPE):
        if not self.is_null():
            if hasattr(self.value, '_FUNC'):
                FUNC = self.value._FUNC
                classname = self.db.record_delegate(FUNC)
            else:
                INSTANCE = self.value._INSTANCE
                classname = self.db.class_name(INSTANCE)
            ns, name = classname.rsplit('::', 1)
            gen.emit('getlex', constants.packagedQName(ns, name))
            return
        super(Avm2ClassConst, self).push_inline(gen, EXPECTED_TYPE)


class Avm2ArrayListConst(Avm2BaseConstMixin, ListConst):

    def _do_not_initialize(self):
        # Check if it is a list of all zeroes:
        try:
            if self.value._list == [0] * len(self.value._list):
                return True
        except:
            pass
        return super(Avm2ListConst, self)._do_not_initialize()
    
    def create_pointer(self, gen):
        llen = len(self.value._list)
        self.db.const_count.inc('List')
        self.db.const_count.inc('List', self.value._TYPE.ITEM)
        self.db.const_count.inc('List', llen)
        gen.oonewarray(self.value._TYPE, llen)

    def initialize_data(self, constgen, gen):
        assert not self.is_null()
        
        # check for special cases and avoid initialization
        if self._do_not_initialize():
            return
        
        for idx, item in enumerate(self.value._array):
            gen.dup()
            gen.emit('setproperty', constants.Multiname(
                    str(idx), constants.PROP_NAMESPACE_SET))

# class CLIDictConst(CLIDictMixin, DictConst):
#     def create_pointer(self, gen):
#         self.db.const_count.inc('Dict')
#         self.db.const_count.inc('Dict', self.value._TYPE._KEYTYPE, self.value._TYPE._VALUETYPE)
#         super(CLIDictConst, self).create_pointer(gen)        