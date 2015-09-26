import numpy as np
from nmrglue.process.proc_base import ifft, fft, rev, cs, tp_hyper, c2ri
import nmrglue.process.pipe_proc as pp
from nmrglue.fileio import bruker, pipe
from nmrglue.fileio.fileiobase import unit_conversion, uc_from_udic
from collections import OrderedDict
from ..utils import make_uc_pipe
from ..NMRFileManager import find_pdata
from copy import deepcopy

class DataUdic(np.ndarray):
    def __new__(cls, data, udic):
        obj = np.asarray(data).view(cls)
        obj.udic = udic
        return obj
        
    def __array_finalize__(self, obj):
        self.udic = getattr(obj, 'udic', None)
        self.history = getattr(obj, 'history', None)
    
    def __array_wrap__(self, obj):
        if obj.shape == ():
            return obj[()]    # if ufunc output is scalar, return it
        else:
            return np.ndarray.__array_wrap__(self, obj)
    
    def tp(self, copy=True, flag='auto'):
        if self.udic['ndim'] < 2: return self
        
        if flag != 'nohyper':
            if (self.udic[0]['complex'] and self.udic[1]['complex']) or\
                flag == 'hyper':
                data = np.array(tp_hyper(self), dtype="complex64")
            else:
                data = self.transpose()
                if self.udic[0]['complex']:
                    data = np.array(c2ri(data), dtype="complex64")
        
        if flag == 'nohyper':                
            data = self.transpose()
        
        # copy the udic and reverse the dimensions
        udic = {k:v for k,v in self.udic.items()}
        temp = udic[0]
        udic[0] = udic[1]
        udic[1] = temp
        
        if copy or (self.nbytes != data.nbytes) or (self.shape != data.shape):
            return DataUdic(data, udic)
        
        if flag == 'nohyper':
            self = self.transpose()
        else:
            self.shape = data.shape
            self.data = data
        self.udic = udic
        
        # TODO: update udic[size]. add 'transposed' to udic?
        return self
    
    def real_part(self):
        return self.di().tp().di().tp()
    
    def di(self):
        dim = self.udic['ndim'] -1
        udic_copy = self.copy_udic()
        udic_copy[dim]['complex'] = False
        return DataUdic(self.real, udic_copy)
    
    def copy_udic(self):
        return deepcopy(self.udic)
    


class NMRSpectrum(DataUdic):
    @classmethod
    def fromFile(cls, file, format):
        method = {
            'Bruker': cls.fromBruker,
            'Pipe': cls.fromPipe
        }[format]

        #dic, data = reader(file)
        return method(file)

    @classmethod
    def fromBruker(cls, file, reverse_data=True, remove_filter=True, read_pdata=True):
        dic, data = bruker.read(file);
        if(read_pdata):
            pdata_file = find_pdata(file, data.ndim)
            
            if(pdata_file is not None):
                data = bruker.read_pdata(pdata_file)[1]
            else: read_pdata = False
        
        if remove_filter and not read_pdata:
            data = bruker.remove_digital_filter(dic, data, True)
    
        u = bruker.guess_udic(dic, data)
        u["original_format"] = 'Bruker'
        u["Name"] = str(file)
        if(read_pdata):
            for i in range(0, data.ndim):
                u[i]['complex'] = False
                u[i]['freq'] = True

        # The data is reversed using the scheme recommened by NMRPipe
        # For details: http://spin.niddk.nih.gov/NMRPipe/ref/nmrpipe/rev.html
        if reverse_data: pass
            #data = rev(data)
            #data = cs(data, 1)
        
        uc = []
        for i in range(0, data.ndim):
            acqus = ['acqus', 'acqu2s', 'acqu3s', 'acqu4s'][i]
            car = dic[acqus]['O1']
            sw = dic[acqus]['SW_h']
            size = u[i]['size']
            obs = dic[acqus]['BF1']
            cplx = u[i]['complex']
            uc.append(unit_conversion(size, cplx, sw, obs, car))

        return cls(data, udic=u, uc=uc)

    @classmethod
    def fromPipe(cls, file):
        dic, data = pipe.read(file)
        if dic['FDTRANSPOSED'] == 1.:
            dic, data = pp.tp(dic, data, auto=True)

        u = pipe.guess_udic(dic, data)
        u["original_format"] = 'Pipe'
        u["Name"] = str(file)
        
        uc = [make_uc_pipe(dic, data, dim) for dim in range(0, data.ndim)]
        #uc = [pipe.make_uc(dic, data, dim) for dim in range(0, data.ndim)]
        # make_uc function orders the dimensions by FDDIMORDER parameter
        # I want the order to match the udic's
        #if dic["FDDIMORDER"][0] == 1.:
        #    uc.reverse()
        
        
        # dic, data = pp.ft(dic, data, auto=True)
        # dic, data = pp.tp(dic, data, auto=True)
        # dic, data = pp.ft(dic, data, auto=True)
        # dic, data = pp.tp(dic, data, auto=True)
        
        #print(data.shape)
        return cls(data, u, uc=uc)

    def __new__(cls, input_array, udic, parent=None, uc=None):
        if input_array.ndim == 1:
            cls = NMRSpectrum1D
        elif input_array.ndim == 2:
            cls = NMRSpectrum2D
        obj = np.asarray(input_array).view(cls)

        
        if parent is None:
            history = OrderedDict()
            history['original'] = lambda s: s
            original = DataUdic(input_array, udic)
        else:
            history = parent.history
            original = parent.original
            if uc is None: uc = parent.uc
        
        # add the new attribute to the created instance
        print(udic['ndim'])
        if uc is None:
            uc = [unit_conversion(udic[i]['size'],
                                    udic[i]['complex'],
                                    udic[i]['sw'],
                                    udic[i]['obs'],
                                    udic[i]['car'])
                for i in range(0, udic['ndim'])]

        if type(uc) is list and len(uc) == 1:
            uc = uc[0]

        
        obj.udic = udic
        obj.uc = uc
        obj.history = history
        obj.original = original
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.udic = getattr(obj, 'udic', None)
        self.uc = getattr(obj, 'uc', None)
        self.history = getattr(obj, 'history', None)
        self.original = getattr(obj, 'original', None)

    ################# Data processing  #####################
    def setData(self, input_array):
        if hasattr(input_array, 'udic'):
            udic = input_array.udic
        else:
            udic = self.udic
            
        if self.nbytes != input_array.nbytes or self.shape != input_array.shape:
            return NMRSpectrum(input_array, udic, self)

        self.data = input_array.data
        self.dtype = input_array.dtype
        self.udic = udic

        return self

    def fapply(self, fun, message):
        self.history[message] = fun
        return self.setData(fun(self))

    def fapplyAtIndex(self, fun, message, idx):
        hist_keys = self.history.keys()
        hist_keys.insert(idx, message)

        hist_funcs = self.history.values()
        hist_funcs.insert(idx, fun)
        self.history = OrderedDict(zip(hist_keys, hist_funcs))
        return self.update_data()

    def fapplyAfter(self, fun, message, element):
        try:
            idx = self.history.keys().index(element) + 1
        except ValueError:
            return self.fapply(fun, message)

        return self.fapplyAtIndex(fun, message, idx)

    def fapplyBefore(self, fun, message, element):
        try:
            idx = self.history.keys().index(element)
        except ValueError:
            return self.fapply(fun, message)

        return self.fapplyAtIndex(fun, message, idx)

    def fapplyAt(self, fun, message, element=None):
        if element is None:
            element = message
        try:
            idx = self.history.keys().index(element)
        except ValueError:
            return self.fapply(fun, message)

        self.history[message] = fun
        return self.update_data()

    
    def update_data(self):
        return self.setData(reduce(lambda x, y: y(x), self.history.values(), self.original))
    
    def getSpectrumAt(self, element, include=False):
        idx = self.history.keys().index(element) + include # if true, include evaluate to 1.
        fn_list = self.history.values()[0:idx]
        return reduce(lambda x, y: y(x), fn_list, self.original)
        
    def original_data(self):
        return self.original

    def time_domain(self):
        if self.udic[0]['freq']:
            return ifft(self)
        else:
            return self

    def freq_domain(self):
        if self.udic[0]['freq']:
            return self
        else:
            return fft(self)
    
    def is_time_domain(self):
        return [self.udic[i]['time'] for i in range(0, self.udic['ndim'])]
    
class NMRSpectrum1D(NMRSpectrum):
    def __array_finalize__(self, obj):
        super(NMRSpectrum1D, self).__array_finalize__(obj)
        #print("final1d")

        #def __array_wrap__(self, obj):
        #    super(NMRSpectrum1D, self).__array_wrap__(obj)


class NMRSpectrum2D(NMRSpectrum):
    def __array_finalize__(self, obj):
        super(NMRSpectrum2D, self).__array_finalize__(obj)
        #print("final2d", getattr(obj, 'uc', None))
        
    # def tp(self, copy=True):
    #     if self.udic[0]['complex'] and self.udic[1]['complex']:
    #         data = np.array(tp_hyper(self), dtype="complex64") #tp_hyper(self)
    #     elif self.udic[1]['complex']:
    #         data = np.array(p.c2ri(data), dtype="complex64")
    #     else:
    #         data = self.transpose()
    #
    #     udic = udic = {k:v for k,v in self.udic.items()}
    #     temp = udic[0]
    #     udic[0] = udic[1]
    #     udic[1] = temp
    #
    #     if copy:
    #         return DataUdic(data, udic)
    #
    #     self.shape = data.shape
    #     self.data = data
    #     self.udic = udic
    #
    #     # TODO: update udic[size]. add 'transposed' to udic?
    #     return self

class NMRDataset():
    def __init__(self, nd, *specs):
        self.nd = nd
        self.specList = list()
        for s in specs:
            self.specList.append(s)

    def __len__(self):
        return len(self.specList)
        
    def __getitem__(self, key):
        return self.specList[key]
        
    
    def __setitem__(self, key, value):
        self.specList[key] = value

    def append(self, s):
        self.specList.append(s)
    
    def pop(self, key):
        return self.specList.pop(key)

class SpecFeature():
    def __init__(self, data, parentSpec):
        self.data = data
        self.spec = parentSpec
        
class SpecLike():
    def __init__(self, data, parentSpec):
        self.data = data
        self.spec = parentSpec

        