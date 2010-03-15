
import py
from mech.fusion.avm2.abc_ import AbcFile

from pypy.translator.oosupport.genoo import GenOO
from pypy.translator.avm2.avm2gen import PyPyAvm2ilasm
from pypy.translator.avm2.constant import Avm2ConstGenerator, Avm2ClassConst, Avm2InstanceConst, Avm2RecordConst, Avm2ArrayListConst
from pypy.translator.avm2.database import LowLevelDatabase
from pypy.translator.avm2.function import Function as TamarinFunction
from pypy.translator.avm2.opcodes import opcodes
from pypy.translator.avm2.types_ import Avm2TypeSystem

class GenAVM2(GenOO):
    
    opcodes    = opcodes
    Function   = TamarinFunction
    Database   = LowLevelDatabase
    TypeSystem = Avm2TypeSystem

    ConstantGenerator = Avm2ConstGenerator

    ClassConst    = Avm2ClassConst
    InstanceConst = Avm2InstanceConst
    RecordConst   = Avm2RecordConst
    ListConst     = Avm2ArrayListConst
    ArrayConst    = Avm2ArrayListConst
    
    def __init__(self, tmpdir, translator, entrypoint, config=None, exctrans=False):
        GenOO.__init__(self, tmpdir, translator, entrypoint, config, exctrans)
        self.const_stat = str(tmpdir.join('const_stat'))
        self.ilasm = None
        self.abc = None
        rtyper = translator.rtyper
        bk = rtyper.annotator.bookkeeper
        clsdef = bk.getuniqueclassdef(Exception)
        ll_Exception = rtyper.exceptiondata.get_standard_ll_exc_instance(rtyper, clsdef)
        self.EXCEPTION = ll_Exception._inst._TYPE
    
    def create_assembler(self):
        self.abc = AbcFile()
        return PyPyAvm2ilasm(self.db, self.abc)

    def generate_source(self):
        if self.ilasm is None:
            self.ilasm = self.create_assembler()
        self.fix_names()
        self.gen_entrypoint()
        self.gen_pendings()
        self.db.gen_constants(self.ilasm)

    def serialize_abc(self):
        return self.abc.serialize()

    # Don't do treebuilding stuff
    # def stack_optimization(self):
    #     pass