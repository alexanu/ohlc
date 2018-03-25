import time, sys, traceback, logging  # noqa
import widdy
from ohlc import colors
from ohlc.colors import modes
from ohlc.candles.candle import CandleChart
from ohlc.types import Ohlc
from ohlc.random import random_ohlc_generator
from threading import Thread  # noqa

log = logging.getLogger(__name__)

# ensure working asyncio for Py2
# import trollius as asyncio

# if sys.version_info.major >= 3: import asyncio
# else:                           import trollius as asyncio

palette = [
    (colors.OK,       'dark green',      'black'),
    (colors.ERR,      'light red',       'black'),

    (colors.BULL,      'dark green',      'black'),
    (colors.BEAR,      'light red',       'black'),
    (colors.BULL_INV,  'black',           'dark green'),
    (colors.BEAR_INV,  'black',           'light red'),

    (colors.SPACE,     'black',           'black', '', 'g19',             'g19'),
    (colors.GREEN,     'dark green,bold', 'black', '', 'dark green,bold', 'g19'),
    (colors.RED,       'dark red,bold',   'black', '', 'dark red,bold',   'g19'),

    (colors.LIME,    'light green',  'black', '', '#0f0', 'g19'),
    (colors.RED,     'dark red',     'black', '', '#f00', 'g19'),
    (colors.FUCHSIA, 'dark magenta', 'black', '', '#f0f', 'g19'),
    (colors.AQUA,    'dark cyan',    'black', '', '#0ff', 'g19'),
    (colors.YELLOW,  'yellow',       'black', '', '#ff0', 'g19'),
    (colors.ORANGE,  'brown',        'black', '', '#f80', 'g19'),
    (colors.GREEN,   'dark green',   'black', '', '#080', 'g19'),
]

class DataSource:
    def __init__(self, source_gen, data_rate=1.0, sink=None):
        """DataSource allows to setup a managed pausable data pipeline.
        After calling `unpause`, you can `send` data to it, which it forwards to `sink.send`.
        You must provide a `sink` in this case. Alternatively, instead of sending data,
        you can also call `next` to get the next value from the original `source_gen` if given.
        You can call `pause` and `unpause` to stop/restart the pipeline.

        Note that a sender should check the `paused` before calling `send` and that the
        DataSource always starts in `paused` mode. Calling `next` is independed of pausing.

        To avoid the `paused` check and having to sleep in external code,
        you can provide a `on_unpause` callback.
        """
        self.source_gen = source_gen
        self.data_rate = data_rate
        self.thread = None
        self.paused = True
        self.sink = sink

    def pause(self):
        if self.paused: return
        self.paused = True
        t = self.thread
        t.join()
        self.thread = None

    def unpause(self):
        self.pause()
        self.thread = t = Thread(target=self.loop)
        t.daemon = True
        t.start()

    def next(self):
        """next returns None if `source_gen` is None or tries to fetch the next value from it.
        Use `next` to bypass the `loop` and directly read values from the source,
        e.g., when paused.
        """
        if self.source_gen is None: return None
        return next(self.source_gen)

    def loop(self):
        """loop runs fetches and forwards data until the DataSource is paused."""
        if self.sink is None: raise ValueError("cannot start data loop without data sink")
        self.paused = False
        t = self.thread
        while not self.paused:
            if t is not self.thread:
                log.warn("found new data thread, stopping current"); break
            v = next(self.source_gen)
            self.sink.send(v)
            if self.data_rate != 0: time.sleep(1.0 / float(self.data_rate))

def random_source(data_rate=1.0, **source_args):
    rgen = random_ohlc_generator(v_start=20.0, v_min=10.0, v_max=100.0)
    source = DataSource(rgen, data_rate=data_rate)
    return source

class CandleApp(widdy.App):
    def __init__(self, source, **chart_args):
        chart_args['border'] = None
        self.chart = CandleChart(**chart_args)
        t, self.update_text = widdy.Text('loading candles...')
        box = widdy.LineBox(t)
        menu = widdy.Menu(
            ('R', colors.OK, 'next ohlc'),
            ('H', colors.OK, 'cycle height'),
            ('W', colors.OK, 'cycle width'),
            ('P', colors.OK, 'play/pause'),
        )
        frame = widdy.Frame(widdy.Header("Candles"), box, menu)
        handlers = widdy.Handlers(
            ('R', self.next_candle),
            ('H', self.resize_height),
            ('W', self.resize_width),
            ('P', self.toggle_pause),
        )
        self.paused = True
        self.source = source
        self.source.sink = self
        super().__init__(frame, handlers=handlers, pal=palette)
        if colors.NUM_COLORS > 0:
            self.screen.set_terminal_properties(colors=colors.NUM_COLORS)

    def resize_height(self):
        x,y = self.screen_size
        h = self.chart.height
        h_max = y - 5
        if h >= h_max: h = 5
        else:          h = min(h_max, int(h * 1.2))
        self.chart.resize(h=h)

    def resize_width(self):
        x,y = self.screen_size
        w = self.chart.width
        w_max = x - 3
        if w >= w_max: w = 20
        else:          w = min(w_max, int(w * 1.2))
        self.chart.resize(w=w)

    def toggle_pause(self):
        if self.source.paused: self.source.unpause()
        else:                  self.source.pause()

    def next_candle(self): self.send(self.source.next())

    def send(self, ohlc:Ohlc):
        try:
            if ohlc is not None: self.chart.add_ohlc(ohlc)
            lines = list(self.chart.format())
            if len(lines) > 0:
                l = lines[0]
                if type(l) is str:
                    raise ValueError("first line is str, expected list, please use urwid render mode")
            self.update_text(list(s + [('','\n')] for s in lines))
        except:
            log.error("faild to add ohlc value: %s", traceback.format_exc())


def main():
    if '-h' in sys.argv or '--help' in sys.argv:
        print('Usage: run without args or use --debug to enable debug output')
        return
    source = random_source(data_rate=10.0)
    app = CandleApp(source, w=60, h=15, color_mode=modes.URWID, heikin=True)
    app.run()


if __name__ == '__main__': main()
