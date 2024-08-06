# ------------------------------------------------------------------------------
# CodeHawk Binary Analyzer
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2021-2024 Aarno Labs LLC
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

from typing import cast, List, Tuple, TYPE_CHECKING

from chb.app.InstrXData import InstrXData

from chb.arm.ARMDictionaryRecord import armregistry
from chb.arm.ARMOpcode import ARMOpcode, simplify_result
from chb.arm.ARMOperand import ARMOperand

import chb.ast.ASTNode as AST
from chb.astinterface.ASTInterface import ASTInterface

from chb.invariants.XXpr import XXpr
import chb.invariants.XXprUtil as XU

import chb.util.fileutil as UF
from chb.util.IndexedTable import IndexedTableValue
from chb.util.loggingutil import chklogger


if TYPE_CHECKING:
    from chb.arm.ARMDictionary import ARMDictionary
    from chb.arm.ARMOperandKind import ARMOffsetAddressOp

@armregistry.register_tag("LDR", ARMOpcode)
class ARMLoadRegister(ARMOpcode):
    """Loads a word from memory and writes it to a register.

    LDR<c> <Rt>, [<base>, <offset>]

    tags[1]: <c>
    args[0]: index of destination operand in armdictionary
    args[1]: index of base register in armdictionary
    args[2]: index of index in armdictionary
    args[3]: index of memory location in armdictionary
    args[4]: is-wide (thumb)

    xdata format:
    -------------
    vars[0]: lhs
    vars[1]: memory location expressed as a variable
    xprs[0]: value in rn
    xprs[1]: value in rm
    xprs[2]: value in memory location
    xprs[3]: value in memory location (simplified)
    xprs[4]: address of memory location
    rdefs[0]: reaching definitions rn
    rdefs[1]: reaching definitions rm
    rdefs[2]: reaching definitions memory location
    rdefs[3..]: reaching definitions for memory value
    uses[0]: use of lhs
    useshigh[0]: use of lhs at high level

    optional:
    vars[2]: lhs base register (if base update), add "bu" to tags

    xprs[.]: instruction condition (if has condition)
    xprs[.]: new address for base register

    uses[1]: use of updated base register
    useshigh[1]: use of updated base register
    """

    def __init__(
            self,
            d: "ARMDictionary",
            ixval: IndexedTableValue) -> None:
        ARMOpcode.__init__(self, d, ixval)
        self.check_key(2, 5, "LoadRegister")

    def mnemonic_extension(self) -> str:
        cc = ARMOpcode.mnemonic_extension(self)
        wide = ".W" if self.args[4] == 1 else ""
        return cc + wide

    @property
    def operands(self) -> List[ARMOperand]:
        return [self.armd.arm_operand(self.args[i]) for i in [0, 3]]

    @property
    def opargs(self) -> List[ARMOperand]:
        return [self.armd.arm_operand(self.args[i]) for i in [0, 1, 2, 3]]

    def is_load_instruction(self, xdata: InstrXData) -> bool:
        return True

    def rhs(self, xdata: InstrXData) -> List[XXpr]:
        return [xdata.xprs[1]]

    def annotation(self, xdata: InstrXData) -> str:
        """lhs, rhs, with optional instr condition and base update."""

        lhs = str(xdata.vars[0])
        rhs = str(xdata.xprs[3])

        xctr = 5
        if xdata.has_instruction_condition():
            pcond = "if " + str(xdata.xprs[xctr]) + " then "
            xctr += 1
        elif xdata.has_unknown_instruction_condition():
            pcond = "if ? then "
        else:
            pcond = ""

        vctr = 2
        if xdata.has_base_update():
            blhs = str(xdata.vars[vctr])
            brhs = str(xdata.xprs[xctr])
            pbupd = "; " + blhs + " := " + brhs
        else:
            pbupd = ""

        if rhs == "??":
            return pcond + lhs + " := *(" + str(xdata.xprs[4]) + ")"

        return pcond + lhs + " := " + rhs + pbupd

    def ast_prov(
            self,
            astree: ASTInterface,
            iaddr: str,
            bytestring: str,
            xdata: InstrXData) -> Tuple[
                List[AST.ASTInstruction], List[AST.ASTInstruction]]:

        memaddr = xdata.xprs[4]

        annotations: List[str] = [iaddr, "LDR", "addr: " + str(memaddr)]

        # low-level assignment

        (ll_rhs, ll_pre, ll_post) = self.opargs[3].ast_rvalue(astree)
        (ll_op1, _, _) = self.opargs[1].ast_rvalue(astree)
        (ll_op2, _, _) = self.opargs[2].ast_rvalue(astree)
        (ll_lhs, _, _) = self.opargs[0].ast_lvalue(astree)

        ll_assign = astree.mk_assign(
            ll_lhs,
            ll_rhs,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)

        # high-level assignment

        lhs = xdata.vars[0]
        rhs = xdata.xprs[3]
        xaddr = xdata.xprs[4]
        rdefs = xdata.reachingdefs
        defuses = xdata.defuses
        defuseshigh = xdata.defuseshigh

        hl_lhs = XU.xvariable_to_ast_lval(lhs, xdata, iaddr, astree, rhs=rhs)
        hl_rhs = XU.xxpr_to_ast_def_expr(rhs, xdata, iaddr, astree, memaddr=xaddr)

        hl_assign = astree.mk_assign(
            hl_lhs,
            hl_rhs,
            iaddr=iaddr,
            bytestring=bytestring,
            annotations=annotations)

        astree.add_instr_mapping(hl_assign, ll_assign)
        astree.add_instr_address(hl_assign, [iaddr])
        astree.add_expr_mapping(hl_rhs, ll_rhs)
        astree.add_lval_mapping(hl_lhs, ll_lhs)
        astree.add_expr_reachingdefs(ll_rhs, rdefs)
        astree.add_lval_defuses(hl_lhs, defuses[0])
        astree.add_lval_defuses_high(hl_lhs, defuseshigh[0])

        if self.opargs[3].is_indirect_register and self.opargs[3].is_write_back:
            addrop = cast("ARMOffsetAddressOp", self.opargs[3].opkind)
            (ll_addr_lhs, _, _) = self.opargs[1].ast_lvalue(astree)
            ll_addr_rhs = addrop.ast_addr_rvalue(astree)

            ll_addr_assign = astree.mk_assign(
                ll_addr_lhs,
                ll_addr_rhs,
                iaddr=iaddr,
                bytestring=bytestring,
                annotations=annotations)
            ll_assigns: List[AST.ASTInstruction] = [ll_assign, ll_addr_assign]

            basereg = xdata.vars[1]
            newaddr = xdata.xprs[4]
            hl_addr_lhs = XU.xvariable_to_ast_lval(basereg, xdata, iaddr, astree)
            hl_addr_rhs = XU.xxpr_to_ast_def_expr(newaddr, xdata, iaddr, astree)

            hl_addr_assign = astree.mk_assign(
                hl_addr_lhs,
                hl_addr_rhs,
                iaddr=iaddr,
                bytestring=bytestring,
                annotations=annotations)
            hl_assigns: List[AST.ASTInstruction] = [hl_assign, hl_addr_assign]

            astree.add_instr_mapping(hl_addr_assign, ll_addr_assign)
            astree.add_instr_address(hl_addr_assign, [iaddr])
            astree.add_expr_mapping(hl_addr_rhs, ll_addr_rhs)
            astree.add_lval_mapping(hl_addr_lhs, ll_addr_lhs)
            astree.add_expr_reachingdefs(ll_addr_rhs, [rdefs[0]])
            astree.add_lval_defuses(ll_addr_lhs, defuses[1])
            astree.add_lval_defuses_high(ll_addr_lhs, defuseshigh[1])
        else:
            ll_assigns = [ll_assign]
            hl_assigns = [hl_assign]

        return (hl_assigns, (ll_pre + ll_assigns + ll_post))
