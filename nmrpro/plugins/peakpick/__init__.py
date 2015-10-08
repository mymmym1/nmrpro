from .peakpick import pick
from .. import JSinput as inp
from ..PluginMount import SpecPlugin, JSCommand

pick_t = lambda data, args: pick(data,{'a':'t', 'thresh':float(args.get('thresh'))})
class PeakPicking(SpecPlugin):
    __version__ = '0.1.0'
    __plugin_name__ = "Peak picking"
    __help__ = ""

    interface = {
    "Analysis":{
        "Peak Picking":{
            "Automatically using CTW":{
                "fun":pick,
                "args":None
            },
            "Peaks below a threshold":{
                "fun":pick_t,
                "args":{'thresh':inp.threshold('Peak Threshold', 'y')}
            },
            "Custom peak picking":{
                "fun":pick,
                'title': 'Peak Picking',
                'args':{
                    'a':inp.select('Peak Picking algorithm', {
                        't':inp.option('Threshold', 
                        {
                            'thresh': inp.threshold('Peak Threshold', 'y'),
                            'msep': inp.num('Minimum sepration between peaks', 0.001, step=0.001, unit='ppm'),
                        }),
                        'c':inp.option('Connected segments', 
                            {'thresh': inp.threshold('Peak Threshold', 'y')}
                        ),
                        'cwt':inp.option('Continuous wavelet transform',
                        {
                            'w':inp.text('Wavelet widths'),
                            'snr':inp.num('Minimum Signal-to-noise ratio', 16, step=0.01),
                        }),
                    }),
                },
            }
        },
    },
    }

class PickCWT(JSCommand):
    menu_path = ['Analysis', 'Peak Picking', 'Automatically using CTW']
    fun = staticmethod(pick)
    nd = [1]
    
class PickThreshold(JSCommand):
    menu_path = ['Analysis', 'Peak Picking', 'Peaks below a Threshold']
    fun = staticmethod(pick_t)
    nd = [1]
    args = {'thresh':inp.threshold('Peak Threshold', 'y')}

class AdvPick(JSCommand):
    menu_path = ['Analysis', 'Peak Picking', 'Custom Peak Picking']
    fun = staticmethod(pick)
    nd = [1]
    args = {
        'a':inp.select('Peak Picking algorithm', {
            't':inp.option('Threshold', 
            {
                'thresh': inp.threshold('Peak Threshold', 'y'),
                'msep': inp.num('Minimum sepration between peaks', 0.001, step=0.001, unit='ppm'),
            }),
            'c':inp.option('Connected segments', 
                {'thresh': inp.threshold('Peak Threshold', 'y')}
            ),
            'cwt':inp.option('Continuous wavelet transform',
            {
                'w':inp.text('Wavelet widths'), #TODO: inp.num
                'snr':inp.num('Minimum Signal-to-noise ratio', 16, step=0.01),
            }),
        }),
    }