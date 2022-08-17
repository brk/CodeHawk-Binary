# ------------------------------------------------------------------------------
# CodeHawk Binary Analyzer
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2021-2022 Aarno Labs LLC
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

from typing import cast, List, Optional, Set, TYPE_CHECKING

import chb.ast.ASTNode as AST
from chb.astinterface.ASTInterface import ASTInterface

import chb.invariants.XXpr as X

import chb.util.fileutil as UF

if TYPE_CHECKING:
    from chb.invariants.VAssemblyVariable import (
        VMemoryVariable, VAuxiliaryVariable, VRegisterVariable)
    from chb.invariants.VConstantValueVariable import (
        VInitialRegisterValue, VInitialMemoryValue, VFunctionReturnValue)
    from chb.invariants.VMemoryOffset import VMemoryOffset
    from chb.mips.MIPSRegister import MIPSRegister


def is_struct_field_address(xpr: X.XXpr, astree: ASTInterface) -> bool:
    """Return true if the expression is the address of a known struct."""

    if xpr.is_int_constant:
        return astree.is_struct_field_address(xpr.intvalue)

    return False


def xxpr_to_struct_field_address_expr(
        xpr: X.XXpr, astree: ASTInterface) -> AST.ASTExpr:
    """Return a struct field as an address expression."""

    if not is_struct_field_address(xpr, astree):
        raise UF.CHBError("Expression " + str(xpr) + " is not a struct field")

    return astree.get_struct_field_address(xpr.intvalue)


def xxpr_list_to_ast_exprs(
        xprs: List[X.XXpr], astree: ASTInterface) -> List[AST.ASTExpr]:

    if all(xpr.is_var for xpr in xprs):
        return xprvariable_list_to_ast_exprs(
            [cast(X.XprVariable, xpr) for xpr in xprs], astree)

    return sum((xxpr_to_ast_exprs(xpr, astree) for xpr in xprs), [])


def xxpr_to_ast_exprs(
        xpr: X.XXpr,
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTExpr]:
    """Convert an XXpr expression into an AST Expr node."""

    if xpr.is_constant:
        return xconstant_to_ast_exprs(cast(X.XprConstant, xpr), astree)

    elif xpr.is_var:
        return xprvariable_to_ast_exprs(
            cast(X.XprVariable, xpr), astree, size=size)

    elif xpr.is_compound:
        return xcompound_to_ast_exprs(cast(X.XprCompound, xpr), astree)

    else:
        raise UF.CHBError(
            "AST conversion of xxpr " + str(xpr) + " not yet supported")


def xconstant_to_ast_exprs(
        xc: X.XprConstant, astree: ASTInterface) -> List[AST.ASTExpr]:
    """Convert a constant value to an AST Expr node."""

    if xc.is_int_constant:
        return [astree.mk_integer_constant(xc.intvalue)]

    else:
        raise UF.CHBError(
            "AST conversion of xconstant " + str(xc) + " not yet supported")


def xprvariable_list_to_ast_exprs(
        xvs: List[X.XprVariable],
        astree: ASTInterface) -> List[AST.ASTExpr]:

    lvals = xvariable_list_to_ast_lvals([xv.variable for xv in xvs], astree)
    return [astree.mk_lval_expression(lval) for lval in lvals]


def xprvariable_to_ast_exprs(
        xv: X.XprVariable,
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTExpr]:
    """Convert a variable to an AST Expr node."""

    lvals = xvariable_to_ast_lvals(xv.variable, astree, size=size)
    return [astree.mk_lval_expression(lval) for lval in lvals]


def xtyped_expr_to_ast_exprs(
        op: str,
        op1: AST.ASTExpr,
        op2: AST.ASTExpr,
        astree: ASTInterface) -> List[AST.ASTExpr]:
    """Determine if expression needs different representation based on type."""

    op1type = op1.ctype(astree.ctyper)

    if op1type is None:
        raise UF.CHBError("Expression is not typed: " + str(op1))

    if op1type.is_pointer and op2.is_integer_constant:
        op2 = cast(AST.ASTIntegerConstant, op2)
        tgttype = cast(AST.ASTTypPtr, op1type).tgttyp
        if tgttype.is_compound:
            ckey = cast(AST.ASTTypComp, tgttype).compkey
            compinfo = astree.compinfo(ckey)
            fieldoffset = field_at_offset(
                compinfo, op2.cvalue, astree)
            lval = astree.mk_memref_lval(op1, fieldoffset)
            return [astree.mk_address_of(lval)]

    return [astree.mk_binary_op(op, op1, op2)]


def xcompound_to_ast_exprs(
        xc: X.XprCompound, astree: ASTInterface) -> List[AST.ASTExpr]:
    """Convert a compound expression to an AST Expr node."""

    op = xc.operator
    operands = xc.operands

    if len(operands) == 1:
        op1s = xxpr_to_ast_exprs(operands[0], astree)
        if len(op1s) == 1:
            op1 = op1s[0]
            return [astree.mk_unary_op(op, op1)]
        else:
            raise UF.CHBError(
                "Multiple operands to unary operation: "
                + ", ".join(str(x) for x in op1s))

    elif len(operands) == 2:

        if xc.is_stack_address:
            stackoffset = xc.stack_address_offset()
            rhslval = astree.mk_stack_variable_lval(stackoffset)
            return [astree.mk_address_of(rhslval)]
        else:
            op1s = xxpr_to_ast_exprs(operands[0], astree)
            op2s = xxpr_to_ast_exprs(operands[1], astree)
            if len(op1s) == 1 and len(op2s) == 1:
                op1 = op1s[0]
                op2 = op2s[0]
                if op in ["plus", "minus"]:
                    try:
                        op1type = op1.ctype(astree.ctyper)
                        return xtyped_expr_to_ast_exprs(op, op1, op2, astree)
                    except:
                        return [astree.mk_binary_op(op, op1, op2)]
                else:
                    return [astree.mk_binary_op(op, op1, op2)]
            elif op == "band" and len(op2s) == 1 and op2s[0].is_integer_constant:
                mask = cast(AST.ASTIntegerConstant, op2s[0])
                if mask.cvalue == 255 and len(op1s) == 4:
                    # op1 is an array of 4 bytes
                    return [op1s[0]]
                elif mask.cvalue == 0:
                    return [astree.mk_integer_constant(0)]
                elif mask.cvalue > 0 and mask.cvalue < 255:
                    return [astree.mk_binary_op(op, op1s[0], op2s[0])]
                else:
                    raise UF.CHBError(
                        "Multiple operands for one or more operands to binary "
                        + "operation: "
                        + op
                        + " on "
                        + "["
                        + ", ".join(str(x) for x in op1s)
                        + "], ["
                        + ", ".join(str(x) for x in op2s)
                        + "]")

            else:
                raise UF.CHBError(
                    "Multiple operands for one or more operands to binary "
                    + "operation: "
                    + op
                    + " on "
                    + "["
                    + ", ".join(str(x) for x in op1s)
                    + "], ["
                    + ", ".join(str(x) for x in op2s)
                    + "]")

    else:
        raise UF.CHBError(
            "AST conversion of compound expression "
            + str(xc)
            + " not yet supported")


def stack_variable_to_ast_lvals(
        offset: "VMemoryOffset",
        astree: ASTInterface,
        size: int = 4,
        ctype: Optional[AST.ASTTyp] = None) -> List[AST.ASTLval]:
    """TODO: split up."""

    if offset.is_constant_value_offset:
        if size == 2:
            v1 = astree.mk_stack_variable_lval(
                offset.offsetvalue(), vtype=ctype)
            v2 = astree.mk_stack_variable_lval(
                offset.offsetvalue() + 1, vtype=ctype)
            return [v1, v2]
        else:
            return [astree.mk_stack_variable_lval(
                offset.offsetvalue(), vtype=ctype)]

    return [astree.mk_named_lval("stack: " + str(offset))]


def field_at_offset(
        compinfo: AST.ASTCompInfo,
        offsetvalue: int,
        astree: ASTInterface) -> AST.ASTOffset:
    (finfo, r) = compinfo.field_at_offset(offsetvalue)

    if finfo.fieldtype.is_compound:
        fieldfkey = cast(AST.ASTTypComp, finfo.fieldtype).compkey
        fcompinfo = astree.compinfo(fieldfkey)
        foffset = field_at_offset(fcompinfo, r, astree)
        return astree.mk_field_offset(
            finfo.fieldname, finfo.compkey, offset=foffset)
    elif r == 0:
        return astree.mk_field_offset(finfo.fieldname, finfo.compkey)
    elif finfo.fieldtype.is_array:
        ftype = cast(AST.ASTTypArray, finfo.fieldtype)
        elsize = astree.type_size_in_bytes(ftype.tgttyp)
        index = r // elsize
        ioffset = astree.mk_scalar_index_offset(index)
        return astree.mk_field_offset(
            finfo.fieldname, finfo.compkey, offset=ioffset)
    else:
        raise UF.CHBError(
            "No field found at offset: "
            + str(offsetvalue)
            + " in struct "
            + compinfo.compname
            + " (Offsets found: "
            + ", ".join(
                (str(f[0])
                 + ":"
                 + str(compinfo.fieldinfo(f[1]).fieldtype)
                 + " "
                 + compinfo.fieldinfo(f[1]).fieldname)
                for f in compinfo.field_offsets.items())
            + ")")


def basevar_variable_to_ast_lvals(
        basevar: "X.XVariable",
        offset: "VMemoryOffset",
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTLval]:

    if offset.is_constant_value_offset:
        offsetvalue = offset.offsetvalue()
        baselvals = xvariable_to_ast_lvals(basevar, astree)
        if len(baselvals) != 1:
            raise UF.CHBError(
                "Multiple baselvals: "
                + ", ".join(str(b) for b in baselvals))
        baselval = baselvals[0]
        basetype = baselval.ctype(astree.ctyper)
        if basetype is not None:
            if basetype.is_array:
                elttype = cast(AST.ASTTypArray, basetype).tgttyp
                eltsize = astree.type_size_in_bytes(elttype)
                index = offsetvalue // eltsize
                indexoffset = astree.mk_scalar_index_offset(index)
                return [astree.mk_lval(baselval.lhost, indexoffset)]
            elif basetype.is_compound:
                fcompkey = cast(AST.ASTTypComp, basetype).compkey
                compinfo = astree.compinfo(fcompkey)
                fieldoffset = field_at_offset(compinfo, offsetvalue, astree)
                return [astree.mk_lval(baselval.lhost, fieldoffset)]
            elif basetype.is_pointer:
                tgttype = cast(AST.ASTTypPtr, basetype).tgttyp
                basexpr = astree.mk_lval_expression(baselval)
                if tgttype.is_scalar:
                    tgtsize = astree.type_size_in_bytes(tgttype)
                    index = offsetvalue // tgtsize
                    indexoffset = astree.mk_scalar_index_offset(index)
                    return [astree.mk_lval(baselval.lhost, indexoffset)]
                elif tgttype.is_compound:
                    fcompkey = cast(AST.ASTTypComp, tgttype).compkey
                    compinfo = astree.compinfo(fcompkey)
                    fieldoffset = field_at_offset(
                        compinfo, offsetvalue, astree)
                    return [astree.mk_memref_lval(basexpr, fieldoffset)]
                elif tgttype.is_void:
                    index = offsetvalue
                    indexoffset = astree.mk_scalar_index_offset(index)
                    return [astree.mk_lval(baselval.lhost, indexoffset)]
                elif offsetvalue == 0:
                    return [astree.mk_memref_lval(basexpr)]
        else:
            index = offsetvalue
            indexoffset = astree.mk_scalar_index_offset(index)
            return [astree.mk_lval(baselval.lhost, indexoffset)]

    return [astree.mk_named_lval(str(basevar) + str(offset))]


def global_variable_to_ast_lvals(
        offset: "VMemoryOffset",
        astree: ASTInterface) -> List[AST.ASTLval]:

    if offset.is_constant_value_offset:
        gaddr = hex(offset.offsetvalue())
        gvinfo = astree.globalsymboltable.global_variable_name(gaddr)
        if gvinfo is not None:
            return [astree.mk_vinfo_lval(gvinfo)]
        else:
            gvname = "gv_" + gaddr
            return [astree.mk_named_lval(
                gvname, globaladdress=offset.offsetvalue())]

    return [astree.mk_named_lval("gv_" + str(offset))]


def vmemory_variable_to_ast_lvals(
        xvmem: "VMemoryVariable",
        astree: ASTInterface,
        size: int = 4,
        ctype: Optional[AST.ASTTyp] = None) -> List[AST.ASTLval]:
    """TODO: split up."""

    if xvmem.base.is_local_stack_frame:
        return stack_variable_to_ast_lvals(
            xvmem.offset, astree, size=size, ctype=ctype)

    elif xvmem.is_basevar_variable:
        return basevar_variable_to_ast_lvals(
            xvmem.basevar, xvmem.offset, astree, size=size)

    elif xvmem.is_global_variable:
        return global_variable_to_ast_lvals(xvmem.offset, astree)

    return [astree.mk_named_lval(str(xvmem))]


def vinitregister_value_list_to_ast_lvals(
        vconstvars: List["VInitialRegisterValue"],
        astree: ASTInterface) -> List[AST.ASTLval]:

    if all(vconstvar.is_argument_value for vconstvar in vconstvars):
        formal_argindices: Set[int] = set([])
        formal_locindices: Set[int] = set([])
        for vconstvar in vconstvars:
            argindex = vconstvar.argument_index()
            (formal, locindices) = astree.get_formal_locindices(argindex)
            formal_argindices.add(formal.argindex)
            for locindex in locindices:
                formal_locindices.add(locindex)

        if len(formal_argindices) == 1:
            # All register arguments refer to the same formal argument
            if len(formal_locindices) == len(formal.arglocs):
                # All components of the formal are covered
                return [astree.mk_formal_lval(formal)]

    return [astree.mk_register_variable_lval(str(vconstvar.register))
            for vconstvar in vconstvars]


def vinitregister_value_to_ast_lvals(
        vconstvar: "VInitialRegisterValue",
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTLval]:

    if vconstvar.is_argument_value:
        argindex = vconstvar.argument_index()
        arglvals = astree.function_argument(argindex)
        if len(arglvals) > 0:
            return arglvals
        else:
            register = str(vconstvar.register)
            return [astree.mk_register_variable_lval(
                register + "_in", registername=register)]

    elif vconstvar.register.is_stack_pointer:
        return [astree.mk_register_variable_lval("base_sp")]
    else:
        register = str(vconstvar.register)
        return [astree.mk_register_variable_lval(
            register + "_in", registername=register)]


def vinitmemory_value_to_ast_lvals(
        vconstvar: "VInitialMemoryValue",
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTLval]:

    xvar = vconstvar.variable

    if xvar.is_memory_variable:
        xvmem = cast("VMemoryVariable", xvar.denotation)
        if xvmem.base.is_local_stack_frame:
            offset = xvmem.offset
            if offset.is_constant_value_offset:
                offsetval = offset.offsetvalue()
                if offsetval >= 0 and (offsetval % 4) == 0:
                    argindex = 4 + (offsetval // 4)
                    flvals = astree.function_argument(argindex)
                    return flvals

    return xvariable_to_ast_lvals(xvar, astree)


def vfunctionreturn_value_to_ast_lvals(
        vconstvar: "VFunctionReturnValue",
        astree: ASTInterface) -> List[AST.ASTLval]:

    vtype: Optional[AST.ASTTyp] = None

    if vconstvar.has_call_target():
        calltarget = str(vconstvar.call_target())
        if astree.has_symbol(calltarget):
            vinfo = astree.get_symbol(calltarget)
            vtype = vinfo.vtype

    return [astree.mk_returnval_variable_lval(vconstvar.callsite, vtype)]


def vauxiliary_variable_list_to_ast_lvals(
        xvauxs: List["VAuxiliaryVariable"],
        astree: ASTInterface) -> List[AST.ASTLval]:

    if all(xvaux.auxvar.is_initial_register_value for xvaux in xvauxs):
        vconstvars = [
            cast("VInitialRegisterValue", xvaux.auxvar) for xvaux in xvauxs]
        return vinitregister_value_list_to_ast_lvals(vconstvars, astree)

    return [astree.mk_named_lval(str(xvaux)) for xvaux in xvauxs]


def vauxiliary_variable_to_ast_lvals(
        xvaux: "VAuxiliaryVariable",
        astree: ASTInterface,
        size: int = 4) -> List[AST.ASTLval]:

    vconstvar = xvaux.auxvar

    if vconstvar.is_initial_register_value:
        vconstvar = cast("VInitialRegisterValue", vconstvar)
        return vinitregister_value_to_ast_lvals(vconstvar, astree, size=size)

    elif vconstvar.is_initial_memory_value:
        vconstvar = cast("VInitialMemoryValue", vconstvar)
        return vinitmemory_value_to_ast_lvals(vconstvar, astree)

    elif vconstvar.is_function_return_value:
        vconstvar = cast("VFunctionReturnValue", vconstvar)
        return vfunctionreturn_value_to_ast_lvals(vconstvar, astree)

    """TODO: split up."""
    return [astree.mk_named_lval(str(xvaux))]


def xvariable_list_to_ast_lvals(
        xvs: List[X.XVariable], astree: ASTInterface) -> List[AST.ASTLval]:

    if all(xv.is_auxiliary_variable for xv in xvs):
        return vauxiliary_variable_list_to_ast_lvals(
            [cast("VAuxiliaryVariable", xv.denotation) for xv in xvs], astree)

    return sum((xvariable_to_ast_lvals(xv, astree) for xv in xvs), [])


def xvariable_to_ast_lvals(
        xv: X.XVariable,
        astree: ASTInterface,
        size: int = 4,
        ctype: Optional[AST.ASTTyp] = None) -> List[AST.ASTLval]:
    """Convert a CHIF variable to an AST Lval node."""

    if xv.is_tmp:
        return [astree.mk_temp_lval()]

    elif xv.is_register_variable:
        xvden = cast("VRegisterVariable", xv.denotation)
        reg = xvden.register
        if reg.is_mips_register:
            mipsreg = cast("MIPSRegister", reg)
            name = "mips_" + mipsreg.name
        else:
            name = str(xv)
        return [astree.mk_register_variable_lval(name)]

    elif xv.is_memory_variable:
        xvmem = cast("VMemoryVariable", xv.denotation)
        return vmemory_variable_to_ast_lvals(
            xvmem, astree, size=size, ctype=ctype)

    elif xv.is_auxiliary_variable:
        xvaux = cast("VAuxiliaryVariable", xv.denotation)
        return vauxiliary_variable_to_ast_lvals(xvaux, astree, size=size)

    else:
        return [astree.mk_named_lval(str(xv))]
