#+
# Animations of Lissajous patterns.
# For background on the maths, see <https://en.wikipedia.org/wiki/Lissajous_curve>.
#
# Copyright 2014 Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
#-

from fractions import \
    Fraction
import math
import anim_common

def draw(g, x_amp, x_freq, x_phase, y_amp, y_freq, y_phase, nr_steps) :

    ratio = Fraction(abs(x_freq), abs(y_freq))
    nr_cycles = min(ratio.numerator, ratio.denominator) # to produce one complete traversal of curve

    def curve_func(x) :
        return \
            (
                math.sin((x + x_phase) * 2 * math.pi * nr_cycles * x_freq) * x_amp,
                math.sin((x + y_phase) * 2 * math.pi * nr_cycles * y_freq) * y_amp,
            )
    #end curve_func

    anim_common.draw_curve(g, f = curve_func, closed = True, nr_steps = nr_steps)
#end draw

def make_draw(x_amp, x_freq, x_phase, y_amp, y_freq, y_phase, nr_steps, do_settings = None) :

    def apply_draw(g, x) :
        if do_settings != None :
            do_settings(g, x)
        #end if
        # note x_freq, y_freq and nr_steps must be integers
        draw \
          (
            g = g,
            x_amp = x_amp(x),
            x_freq = round(x_freq(x)),
            x_phase = x_phase(x),
            y_amp = y_amp(x),
            y_freq = round(y_freq(x)),
            y_phase = y_phase(x),
            nr_steps = round(nr_steps(x))
          )
    #end apply_draw

    x_amp = anim_common.ensure_interpolator(x_amp)
    x_freq = anim_common.ensure_interpolator(x_freq)
    x_phase = anim_common.ensure_interpolator(x_phase)
    y_amp = anim_common.ensure_interpolator(y_amp)
    y_freq = anim_common.ensure_interpolator(y_freq)
    y_phase = anim_common.ensure_interpolator(y_phase)
    nr_steps = anim_common.ensure_interpolator(nr_steps)
    return \
        apply_draw
#end make_draw

