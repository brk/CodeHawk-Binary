# ------------------------------------------------------------------------------
# CodeHawk Binary Analyzer
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2021-2024  Aarno Labs LLC
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
"""Superclass of a basic block for different architectures.

Subclasses:
 - ARMBlock
 - AsmBlock
 - MIPSBlock
"""

import hashlib
import xml.etree.ElementTree as ET

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Mapping, Optional, Sequence, TYPE_CHECKING

from chb.app.Instruction import Instruction

import chb.ast.ASTNode as AST
from chb.astinterface.ASTInterface import ASTInterface

from chb.invariants.XXpr import XXpr
from chb.jsoninterface.JSONResult import JSONResult

import chb.util.fileutil as UF

if TYPE_CHECKING:
    import chb.app.Function


class BasicBlock(ABC):

    def __init__(
            self,
            xnode: ET.Element) -> None:
        self.xnode = xnode

    @property
    def baddr(self) -> str:
        _baddr = self.xnode.get("ba")
        if _baddr is None:
            raise UF.CHBError("Basic block address is missing from xml")
        return _baddr

    @property
    def real_baddr(self) -> str:
        _baddr = self.baddr
        if _baddr.startswith("F"):
            return _baddr.split("_")[-1]
        else:
            return _baddr

    @property
    def lastaddr(self) -> str:
        return sorted(self.instructions.keys())[-1]

    @property
    def real_lastaddr(self) -> str:
        _addr = self.lastaddr
        if _addr.startswith("F"):
            return _addr.split("_")[-1]
        else:
            return _addr

    @property
    def last_instruction(self) -> Instruction:
        lastaddr = sorted(self.instructions.keys())[-1]
        return self.instructions[lastaddr]

    @property
    def has_return(self) -> bool:
        return self.last_instruction.is_return_instruction

    @property
    @abstractmethod
    def instructions(self) -> Mapping[str, Instruction]:
        ...

    @property
    def call_instructions(self) -> Sequence[Instruction]:
        result: List[Instruction] = []
        for (ia, instr) in sorted(self.instructions.items()):
            if instr.is_call_instruction:
                result.append(instr)
        return result

    @property
    def jump_instructions(self) -> Sequence[Instruction]:
        result: List[Instruction] = []
        for (ia, instr) in sorted(self.instructions.items()):
            if instr.is_jump_instruction:
                result.append(instr)
        return result

    @property
    def store_instructions(self) -> Sequence[Instruction]:
        result: List[Instruction] = []
        for (ia, instr) in sorted(self.instructions.items()):
            if instr.is_store_instruction:
                result.append(instr)
        return result

    @property
    def load_instructions(self) -> Sequence[Instruction]:
        result: List[Instruction] = []
        for (ia, instr) in sorted(self.instructions.items()):
            if instr.is_load_instruction:
                result.append(instr)
        return result

    def has_instruction(self, iaddr: str) -> bool:
        return iaddr in self.instructions

    def instruction(self, iaddr: str) -> Instruction:
        if iaddr in self.instructions:
            return self.instructions[iaddr]
        raise UF.CHBError("Instruction " + iaddr + " not found")

    def md5(self) -> str:
        m = hashlib.md5()
        for instr in self.instructions.values():
            m.update(instr.bytestring.encode("utf-8"))
        return m.hexdigest()

    def rev_md5(self) -> str:
        """Use reverse bytestring to account for difference in endianness."""

        m = hashlib.md5()
        for instr in self.instructions.values():
            m.update(instr.rev_bytestring.encode("utf-8"))
        return m.hexdigest()

    @abstractmethod
    def to_string(
            self,
            bytes: bool = False,
            opcodetxt: bool = True,
            opcodewidth: int = 25,
            sp: bool = True) -> str:
        ...

    def to_json_result(self) -> JSONResult:
        raise NotImplementedError("BasicBlock.to_json_result")

    def __str__(self) -> str:
        return self.to_string()
