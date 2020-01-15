# ------------------------------------------------------------------------------
# Access to the CodeHawk Binary Analyzer Analysis Results
# Author: Henny Sipma
# ------------------------------------------------------------------------------
# The MIT License (MIT)
#
# Copyright (c) 2016-2020 Kestrel Technology LLC
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

import os
import zipfile
import xml.etree.ElementTree as ET

import chb.util.fileutil as UF

from chb.models.DllEnumDefinition import DllEnumDefinition
from chb.models.DllSummary import DllSummary
from chb.models.DllSummaryRef import DllSummaryRef

class StdPESummaries(object):

    def __init__(self,models,jarfilename):
        self.models = models
        self.jarfile = zipfile.ZipFile(jarfilename,'r')
        self.filenames = []
        self.dllsummaries = {}    # (dll,fname) -> DllSummary
        self.jnisummaries = {}    # index -> JniSummary
        self.constantdefs = {}    # name ->  PEConstantDef
        self.allsummariesloaded = False
        for info in self.jarfile.infolist():
            self.filenames.append(info.filename)

    def _get_filename(self,dll,fname):
        name = dll.lower().replace('.','_') + os.sep + fname + '.xml'
        if name in self.filenames:
            return name
        name = dll.lower().replace('.','_') + '_dll' + os.sep + fname + '.xml'
        if name in self.filenames:
            return name
        return None

    def _get_enum_filename(self,name):
        filename = os.path.join('constants',name.lower() + '.xml')
        if filename in self.filenames:
            return filename

    def has_summary(self,dll,fname):
        return not (self._get_filename(dll,fname) is None)

    def get_summary(self,dll,fname):
        if self.has_summary(dll,fname):
            if not (dll,fname) in self.dllsummaries:
                self._read_summary(dll,fname)
            return self.dllsummaries[(dll,fname)]
        else:
            raise UF.CHBError('Summary for ' + dll + ':' + fname + ' not found')

    def has_enum_definition(self,name):
        if name in self.constantdefs: return True
        else:
            self._read_enum_definition(name)
            return name in self.constantdefs

    def get_enum_constant(self,enumname,value):
        if self.has_enum_definition(enumname):
            enumdef = self.constantdefs[enumname]
            return enumdef.get_name(value)

    def _read_summary(self,dll,fname):
        def isref(xnode): return (not (xnode.find('refer-to') is None))
        xnode = self.get_summary_xnode(dll,fname)
        if xnode is None:
            raise UF.CHBError('Summary for ' + dll + ':' + fname + ' may be corrupted')
        if isref(xnode):
            refnode = xnode.find('refer-to')
            self.dllsummaries[(dll,fname)] = DllSummaryRef(self.models,refnode,dll,fname)
        else:
            self.dllsummaries[(dll,fname)] = DllSummary(self.models,xnode)

    def get_summary_xnode(self,dll,fname):
        filename = self._get_filename(dll,fname)
        if filename is None:
            raise UF.CHBError('Error in obtaining summary for ' + dll + ':' + fname)
        zfile = self.jarfile.read(filename).decode('utf-8')
        try:
            xnode = ET.fromstring(str(zfile)).find('libfun')
        except ET.ParseError as e:
            raise UF.CHBError('Parse error in file ' + filename + ' for '
                                 + dll + ':' + fname + ':' + str(e))
        except UnicodeEncodeError as e:
            raise UF.CHBError('Unicode error in file ' + filename + ' for '
                                 + dll + ':' + fname + ':' + str(e))
        if xnode is None:
            raise UF.CHBError('Unable to load summary for ' + dll + ':' + fname
                                 + ': libfun node not found')
        return xnode

    def _read_enum_definition(self,name):
        xnode = self.get_enum_definition_xnode(name)
        if xnode is None: return
        self.constantdefs[name] = DllEnumDefinition(self,xnode)

    def get_enum_definition_xnode(self,name):
        filename = self._get_enum_filename(name)
        if filename is None:
            return None
        zfile = self.jarfile.read(filename)
        return ET.fromstring(str(zfile.decode('utf-8'))).find('symbolic-constants')

        
