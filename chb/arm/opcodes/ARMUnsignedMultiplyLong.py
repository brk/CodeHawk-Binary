# ------------------------------------------------------------------------------
# CodeHawk Binary Analyzer
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2021-2025 Aarno Labs LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ------------------------------------------------------------------------------

from typing import List, Tuple, TYPE_CHECKING

from chb.app.InstrXData import InstrXData

from chb.arm.ARMDictionaryRecord import armregistry
from chb.arm.ARMOpcode import ARMOpcode, ARMOpcodeXData, simplify_result
from chb.arm.ARMOperand import ARMOperand

import chb.ast.ASTNode as AST
from chb.astinterface.ASTInterface import ASTInterface

import chb.invariants.XXprUtil as XU

import chb.util.fileutil as UF
from chb.util.IndexedTable import IndexedTableValue
from chb.util.loggingutil import chklogger

if TYPE_CHECKING:
    from chb.arm.ARMDictionary import ARMDictionary
    from chb.invariants.XVariable import XVariable
    from chb.invariants.XXpr import XXpr


class ARMUnsignedMultiplyLongXData(ARMOpcodeXData):

    def __init__(self, xdata: InstrXData) -> None:
        ARMOpcodeXData.__init__(self, xdata)

    @property
    def vlo(self) -> "XVariable":
        return self.var(0, "vlo")

    @property
    def vhi(self) -> "XVariable":
        return self.var(1, "vhi")

    @property
    def xrn(self) -> "XXpr":
        return self.xpr(0, "xrn")

    @property
    def xrm(self) -> "XXpr":
        return self.xpr(1, "xrm")

    @property
    def result(self) -> "XXpr":
        return self.xpr(2, "result")

    @property
    def rresult(self) -> "XXpr":
        return self.xpr(3, "rresult")

    @property
    def result_simplified(self) -> str:
        return simplify_result(
            self.xdata.args[4], self.xdata.args[5], self.result, self.rresult)

    @property
    def annotation(self) -> str:
        assignment = str(self.vlo) + " := " + self.result_simplified
        return self.add_instruction_condition(assignment)


@armregistry.register_tag("UMULL", ARMOpcode)
class ARMUnsignedMultiplyLong(ARMOpcode):
    """Multiplies two unsigned 32-bit signed values to produce a 64-bit result

    UMULL{S}<c> <RdLo>, <RdHi>, <Rn>, <Rm>

    tags[1]: <c>
    args[0]: flags are set
    args[1]: index of RdLo in armdictionary
    args[2]: index of RdHi in armdictionary
    args[3]: index of Rn in armdictionary
    args[4]: index of Rm in armdictionary

    xdata format: a:vvxxxxrrddhh
    ----------------------------
    vars[0]: lhs1 (RdLo)
    vars[1]: lhs2 (RdHi)
    xprs[0]: rhs1 (Rn)
    xprs[1]: rhs2 (Rm)
    xprs[2]: rhs1 * rhs2
    xprs[3]: rhs1 * rhs2 (simplified)
    rdefs[1]: rhs1 (Rn)
    rdefs[2]: rhs2 (Rm)
    uses[0]: lhs1 (RdLo)
    uses[1]: lhs2 (RdHi)
    useshigh[0]: lhs1 (RdLo)
    useshigh[1]: lhs2 (RdHi)
    """

    def __init__(self, d: "ARMDictionary", ixval: IndexedTableValue) -> None:
        ARMOpcode.__init__(self, d, ixval)
        self.check_key(2, 5, "UnsignedMultiplyLong")

    @property
    def operands(self) -> List[ARMOperand]:
        return [self.armd.arm_operand(i) for i in self.args[1:]]

    @property
    def opargs(self) -> List[ARMOperand]:
        return [self.armd.arm_operand(i) for i in self.args[1:]]

    def annotation(self, xdata: InstrXData) -> str:
        xd = ARMUnsignedMultiplyLongXData(xdata)
        if xd.is_ok:
            return xd.annotation
        else:
            return "Error value"

    def assembly_ast(
            self,
            astree: ASTInterface,
            iaddr: str,
            bytestring: str,
            xdata: InstrXData) -> List[AST.ASTInstruction]:

        annotations: List[str] = [iaddr, "UMULL"]

        (rhs1, preinstrs1, postinstrs1) = self.operands[2].ast_rvalue(astree)
        (rhs2, preinstrs2, postinstrs2) = self.operands[3].ast_rvalue(astree)
        (lhs1, _, _) = self.operands[0].ast_lvalue(astree)
        (lhs2, _, _) = self.operands[1].ast_lvalue(astree)
        binop = astree.mk_binary_op("mult", rhs1, rhs2)
        zero = astree.mk_integer_constant(0)
        assign1 = astree.mk_assign(
            lhs1,
            binop,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=(annotations + ["low"]))
        assign2 = astree.mk_assign(
            lhs2,
            zero,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)
        return preinstrs1 + preinstrs2 + [assign1, assign2] + postinstrs1 + postinstrs2

    # --------------------------------------------------------------------------
    # Operation
    # result = UInt(R[n]) * UInt(R[m]);
    # R[dHi] = result<63:32>;
    # R[dLo] = result<31:0>;
    # if setflags then
    #   APSR.N = result<63>;
    #   APSR.Z = IsZeroBit(result<63:0>);
    # --------------------------------------------------------------------------
    def ast_prov(
            self,
            astree: ASTInterface,
            iaddr: str,
            bytestring: str,
            xdata: InstrXData) -> Tuple[
                List[AST.ASTInstruction], List[AST.ASTInstruction]]:

        annotations: List[str] = [iaddr, "UMULL"]

        # low-level assignments

        (ll_lhslo, _, _) = self.opargs[0].ast_lvalue(astree)
        (ll_lhshi, _, _) = self.opargs[1].ast_lvalue(astree)
        (ll_op1, _, _) = self.opargs[2].ast_rvalue(astree)
        (ll_op2, _, _) = self.opargs[3].ast_rvalue(astree)
        ll_result = astree.mk_binary_op("mult", ll_op1, ll_op2)
        masklo = astree.mk_integer_constant(0xffffffff)
        shifthi = astree.mk_integer_constant(32)
        ll_lo_result = astree.mk_binary_op("and", ll_result, masklo)
        ll_hi_result = astree.mk_binary_op("lsr", ll_result, shifthi)

        ll_assign_lo = astree.mk_assign(
            ll_lhslo,
            ll_lo_result,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)
        ll_assign_hi = astree.mk_assign(
            ll_lhshi,
            ll_hi_result,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)

        # high-level assignments

        xd = ARMUnsignedMultiplyLongXData(xdata)
        if not xd.is_ok:
            chklogger.logger.error(
                "Encountered error value at address %s", iaddr)
            return ([], [])

        lhs1 = xd.vlo
        lhs2 = xd.vhi
        rhs1 = xd.xrn
        rhs2 = xd.xrm
        result = xd.rresult
        rdefs = xdata.reachingdefs
        defuses = xdata.defuses
        defuseshigh = xdata.defuseshigh

        hl_lhslo = XU.xvariable_to_ast_lval(lhs1, xdata, iaddr, astree)
        hl_lhshi = XU.xvariable_to_ast_lval(lhs2, xdata, iaddr, astree)

        hl_rhslo = XU.xxpr_to_ast_def_expr(result, xdata, iaddr, astree)
        hl_rhshi = astree.mk_binary_op(
            "lsr", hl_rhslo, astree.mk_integer_constant(32))

        hl_assign_lo = astree.mk_assign(
            hl_lhslo,
            hl_rhslo,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)
        hl_assign_hi = astree.mk_assign(
            ll_lhshi,
            hl_rhshi,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)

        astree.add_instr_mapping(hl_assign_lo, ll_assign_lo)
        astree.add_instr_mapping(hl_assign_hi, ll_assign_hi)
        astree.add_instr_address(hl_assign_lo, [iaddr])
        astree.add_expr_mapping(hl_rhslo, ll_lo_result)
        astree.add_lval_mapping(hl_lhslo, ll_lhslo)
        astree.add_expr_reachingdefs(ll_op1, [rdefs[0]])
        astree.add_expr_reachingdefs(ll_op2, [rdefs[1]])
        astree.add_lval_defuses(hl_lhslo, defuses[0])
        astree.add_lval_defuses(hl_lhshi, defuses[1])
        astree.add_lval_defuses_high(hl_lhslo, defuseshigh[0])
        astree.add_lval_defuses_high(hl_lhshi, defuseshigh[1])

        return ([hl_assign_lo, hl_assign_hi], [ll_assign_lo, ll_assign_hi])
