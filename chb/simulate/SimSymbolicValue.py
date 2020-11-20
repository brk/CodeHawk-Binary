# ------------------------------------------------------------------------------
# Access to the CodeHawk Binary Analyzer Analysis Results
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2016-2020 Kestrel Technology LLC
# Copyright (c) 2020      Henny Sipma
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

import chb.util.fileutil as UF
import chb.simulate.SimUtil as SU
import chb.simulate.SimValue as SV

# convenience functions

def mk_global_address(offset):    # integer
    return SimGlobalAddress(SV.mk_simvalue(offset))

def mk_stack_address(offset):     # integer
    return SimStackAddress(SV.mk_simvalue(offset))

def mk_base_address(base,offset=0,buffersize=None,tgttype=None):
    """Makes a base address with offset (int) and buffer size (simvalue)."""
    return SimBaseAddress(base,
                          SV.mk_simvalue(offset),
                          buffersize=buffersize,
                          tgttype=tgttype)

def mk_string_address(s): return SimStringAddress(s)

def mk_symbol(name,type=None,minval=None,maxval=None):
    return SimSymbol(name,type=type,minval=minval,maxval=maxval)

def mk_filepointer(filename,filepointer):
    return SimSymbolicFilePointer(filename,filepointer)

def mk_filedescriptor(filename,filedescriptor):
    return SimSymbolicFileDescriptor(filename,filedescriptor)

class SimSymbolicValue(SV.SimValue):

    def __init__(self):
        SV.SimValue.__init__(self)
        self.expressions = []
        
    def is_symbolic(self): return True

    def is_address(self): return False
    def is_string_address(self): return False
    def is_symbol(self): return False
    def is_environment_string(self): return False
    def is_environment_string_entry(self): return False
    def is_tainted_data(self): return False
    def is_file_pointer(self): return False
    def is_file_descriptor(self): return False

    def __str__(self): return 'symbolic value'

class SimAddress(SimSymbolicValue):

    def __init__(self,base,offset):
        SimSymbolicValue.__init__(self)
        self.base = base         # 'global', 'stack', baseaddress
        self.offset = offset     # SimDoubleWordValue

    def is_address(self): return True

    def is_aligned(self,size=4): return (self.offset.value % size) == 0

    def is_defined(self): return self.offset.is_defined()

    def is_global_address(self): return False
    def is_stack_address(self): return False
    def is_base_address(self): return False

    def get_offset(self): return self.offset

    def get_alignment(self): return self.get_offset_value() % 4

    def get_offset_value(self):
        if self.offset.is_defined():
            return self.offset.to_signed_int()
        else:
            raise UF.CHBError('Address offset is not defined: ' + str(self))

    def to_hex(self): return hex(self.offset.value)

    def __str__(self): return self.base + ':' + str(self.to_hex())


class SimGlobalAddress(SimAddress):

    def __init__(self,offset):
        SimAddress.__init__(self,'global',offset)

    def is_global_address(self): return True

    def add(self,simval): return self.add_offset(simval.to_signed_int())

    def sub(self,simval): return self.add_offset(-simval.to_signed_int())

    def add_offset(self,intval):
        newoffset = self.offset.add(SV.SimDoubleWordValue(intval))
        return SimGlobalAddress(newoffset)

    def __str__(self): return str(self.to_hex())


class SimStackAddress(SimAddress):

    def __init__(self,offset):
        SimAddress.__init__(self,'stack',offset)

    def is_equal(self,other):
        if other.is_symbolic() and other.is_stack_address():
            if self.get_offset_value() == other.get_offset_value():
                return SV.SimBoolValue(1)
        return SV.SimBoolValue(0)

    def is_not_equal(self,other):
        if other.is_symbolic() and other.is_stack_address():
            if self.get_offset_value() == other.get_offset_value():
                return SV.SimBoolValue(0)
        return SV.SimBoolValue(1)

    def add_offset(self,intval):
        newoffset = self.offset.add(SV.SimDoubleWordValue(intval))      
        return SimStackAddress(newoffset)

    def add(self,simval): return self.add_offset(simval.to_signed_int())

    def sub(self,simval): return self.add_offset(-simval.to_signed_int())

    def subu(self,simval):
        if simval.is_literal() and simval.is_defined():
            return self.add_offset(-simval.to_unsigned_int())
        elif simval.is_stack_address():
            return SV.mk_simvalue(self.get_offset_value() - simval.get_offset_value())
        else:
            return self.add_offset(-simval.to_unsigned_int())

    def add_unsigned(self,simval): return self.add_offset(simval.to_unsigned_int())

    def bitwise_and(self,simval):
        newoffset = self.offset.bitwise_and(simval)
        return SimStackAddress(newoffset)

    def is_stack_address(self): return True

    def __str__(self): return str('stack:' + str(self.offset.to_signed_int()))

class SimBaseAddress(SimAddress):

    def __init__(self,base,offset,buffersize=None,tgttype=None):
        SimAddress.__init__(self,base,offset)
        self.buffersize = buffersize
        self.tgttype = tgttype

    def is_equal(self,other):
        if other.is_literal() and other.is_defined() and other.is_zero():
            return SV.simfalse

    def is_not_equal(self,other):
        if other.is_literal() and other.is_defined() and other.is_zero():
            return SV.simtrue

    def add_offset(self,intval):
        newoffset = self.offset.add(SV.SimDoubleWordValue(intval))
        return SimBaseAddress(self.base,newoffset,buffersize=self.buffersize)

    def get_base(self): return self.base

    def add(self,simval): return self.add_offset(simval.to_signed_int())

    def sub(self,simval): return self.add_offset(-simval.to_signed_int())

    def add_unsigned(self,simval): return self.add_offset(simval.to_unsigned_int())

    def is_base_address(self): return True

    def has_buffer_size(self): return not self.buffersize is None

    def get_buffer_size(self): return self.buffersize

    def has_target_type(self): return not self.tgttype is None

    def get_target_type(self): return self.tgttype

    def __str__(self): return self.base + ':' + str(self.offset.to_signed_int())


class SimStringAddress(SimSymbolicValue):

    def __init__(self,stringval):
        SimSymbolicValue.__init__(self)
        self.stringval = stringval

    def is_string_address(self): return True

    def add(self,v):
        if v.is_literal() and v.is_defined():
            if v.value == 0:
                return self
            elif v.value > 0:
                if len(self.stringval) > v.value:
                    return mk_string_address(self.stringval[v.value:])
                else:
                    raise UF.CHBError('Cannot add ' + str(v.value)
                                      + ' to string of length: '
                                      + str(len(self.stringval)))
            else:
                raise UF.CHBError('Unable to add negative number to string address: '
                                  + str(v.value))
        else:
            raise UF.CHBError('String address: value to be added is undefined')

    def get_string(self):
        """Return string pointed to by this address."""
        return self.stringval

    def __str__(self): return 'string:' + self.stringval


class SimSymbol(SimSymbolicValue):

    def __init__(self,name,type=None,minval=None,maxval=None):
        SimSymbolicValue.__init__(self)
        self.name = name
        self.type = type
        self.minval = minval
        self.maxval = maxval

    def is_symbol(self): return True

    def is_equal(self,other):
        return SV.simfalse    # not equal to anything

    def is_not_equal(self,other):
        return SV.simfalse

    def is_non_negative(self):
        if self.has_minval():
            if self.minval >= 0:
                return SV.simtrue
            else:
                return SV.simfalse
        else:
            return SV.simUndefinedBool

    def is_negative(self):
        if self.has_minval():
            if self.minval >= 0:
                return SV.simfalse
            else:
                return SV.simtrue
        else:
            return SV.simUndefinedBool

    def has_minval(self): return not self.minval is None

    def has_maxval(self): return not self.maxval is None

    def has_type(self): return not self.type is None

    def get_minval(self): return self.minval

    def get_maxval(self): return self.maxval

    def get_type(self): return self.type

    def get_name(self): return self.name

    def __str__(self):
        ptype = '[type:' + self.type + ']' if self.has_type() else ''
        if self.has_minval() and self.has_maxval():
            prange = ' [' + str(self.minval) + '..' + str(self.maxval) + ']'
        elif self.has_minval():
            prange = ' [' + str(self.minval) + '... ]'
        elif self.has_maxval():
            prange = ' [ ... ' + str(maxval) + ']'
        else:
            prange = ''
        return 'sym:' + self.name + ptype + prange

class SimSymbolicFilePointer(SimSymbol):

    def __init__(self,filename,fp):
        SimSymbol.__init__(self,filename + '_filepointer',type='ptr2FILE')
        self.filename = filename
        self.fp = fp

    def is_file_pointer(self): return True

    def is_not_equal(self,other):
        if other.is_literal() and other.is_defined():
            if other.value == 0:
                return SV.simtrue
        raise UF.CHBError('SimSymbolicFilePointer.equal(' + str(other) + ')')

    def is_equal(self,other):
        if other.is_literal() and other.is_defined():
            if other.value == 0:
                return SV.simfalse
        raise UF.CHBError('SimSymbolicFilePointer.equal(' + str(other) + ')')

    def __str__(self): return 'fp_' + self.filename

class SimSymbolicFileDescriptor(SimSymbol):

    def __init__(self,filename,fd):
        SimSymbol.__init__(self,filename + '_filedescriptor',type='int')
        self.filename = filename
        self.fd = fd

    def is_file_descriptor(self): return True

    def is_non_negative(self): return SV.simtrue

    def is_not_equal(self,other):
        if other.is_literal() and other.is_defined() and other.to_signed_int() == -1:
            return SV.simtrue
        else:
            return SV.simfalse

    def __str__(self): return 'fd_' + self.filename


class SimEnvironmentString(SimSymbolicValue):

    def __init__(self,offset):
        SimSymbolicValue.__init__(self)
        self.offset = offset # integer

    def is_environment_string(self): return True

    def __str__(self): return 'env:' + str(self.offset)

class SimEnvironmentStringEntry(SimSymbolicValue):
    """Element of the environment string (environment string dereferenced)."""

    def __init__(self,entryoffset):
        SimSymbolicValue.__init__(self)
        self.entryoffset = entryoffset    # integer

    def is_environment_string_entry(self): return True

    def __str__(self): return 'env[' + str(self.entryoffset) + ']'


class SimTaintedData(SimSymbolicValue):
    """Super class for different kinds of tainted data."""

    def __init__(self,source):
        SimSymbolicValue.__init__(self)
        self.source = source    # source of the taint

    def is_tainted_data(self): return True

    def is_tainted_string(self): return False
    def is_tainted_value(self): return False

    def __str__(self): return 'tainted[' + self.source + ']'


class SimTaintedString(SimTaintedData):

    def __init__(self,source,length=None,maxlen=None):
        SimTaintedData.__init__(self,source)
        self.length = len
        self.maxlen = maxlen

    def is_tainted_string(self): return True

    def has_length(self): return not self.length is None

    def has_maxlen(self): return not self.maxlen is None

    def get_length(self): return self.length

    def get_maxlen(self): return self.maxlen


class SimTaintedValue(SimTaintedData):

    def __init__(self,source,width,minval=None,maxval=None):
        SimTaintedData.__init__(self,source)
        self.width = width    # number of bytes
        self.minval = minval
        self.maxval = maxval

    def is_not_equal(self,other):
        if (other.is_literal() and other.is_defined()
            and self.minval and self.maxval):
            if other.value < self.minval or other.value > self.maxval:
                return SV.simtrue
        self.expressions.append(('self <',other))
        return SV.simUndefinedBool

    def is_tainted_value(self): return True

    def get_width(self): return self.width

    def has_minval(self): return not self.minval is None

    def has_maxval(self): return not self.maxval is None

    def get_minval(self): return self.minval

    def get_maxval(self): return self.maxval
        
        
