"""Framework for doing various animations of drawing into a Cairo
graphics context.

An “interpolator” is a function of a scalar value x (representing the
current animation time) and returning anything. The result from an
interpolator is typically passed to a Cairo drawing routine, or to
some code that uses it for Cairo drawing.

A “draw procedure” takes two arguments (g, t), g being a qahirah.Context
into which to draw the current frame, and t being the current animation time.
It can invoke whatever Cairo drawing commands it needs to, taking account
of the animation time in whatever way it chooses, to render the current
frame image into the given Context.

This whole framework is based around heavy use of these two kinds of
routines. A draw procedure will typically invoke interpolators on its
time argument, and use whatever they return as arguments to drawing
commands.

You can write your own interpolators and draw procedures from scratch:
provided they take the right arguments and (in the case of interpolators)
are identified to the framework as interpolators (using the “interpolator”
decorator provided below) and return suitable results, the framework
will work with them. However, you will probably want to take advantage
of the features provided by this module to make things easier. This
module provides various predefined forms of interpolator, several useful
ways of generating and combining interpolators, and a variety of generators
of draw procedures that will automatically take interpolator arguments into
account.

For example, the make_draw routine will take a sequence of named methods
on qahirah.Context objects and corresponding tuples of arguments to them,
where the latter can contain any mixture of constant values and interpolators.
The resultant draw procedure will invoke the specified sequence of drawing
calls, automatically applying any interpolators to the current animation
time to determine the corresponding argument values for that time.
"""
#+
# Copyright 2014, 2015 by Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
# Licensed under CC-BY-SA <http://creativecommons.org/licenses/by-sa/4.0/>.
#-

from types import \
    FunctionType
import os
import math
import qahirah as qah

#+
# Interpolators
#-

def interpolator(f) :
    "marks f as an interpolator. All functions to be used as interpolators" \
    " must be put through this."
    f.is_interpolator = True
    return f
#end interpolator

def is_interpolator(f) :
    "checks if f is an interpolator function."
    return type(f) == FunctionType and hasattr(f, "is_interpolator") and f.is_interpolator
#end is_interpolator

def constant_interpolator(y) :
    "returns a function of x that always returns the same constant value y."
    return \
        interpolator(lambda x : y)
#end constant_interpolator

def ensure_interpolator(f) :
    "ensures f is an interpolator, by creating a constant interpolator returning f if not."
    return \
        f if is_interpolator(f) else constant_interpolator(f)
#end ensure_interpolator

def linear_interpolator(from_x, to_x, from_y, to_y) :
    "returns a function of x in the range [from_x .. to_x] which returns" \
    " the corresponding linearly-interpolated value in the range [from_y .. to_y]."
    return \
        interpolator(lambda x : (x - from_x) / (to_x - from_x) * (to_y - from_y) + from_y)
#end linear_interpolator

def ease_inout_interpolator(x0, x1, x2, x3, from_y, to_y) :
    "returns a function of x in the range [x0 .. x3] which interpolates over [from_y .. to_y]." \
    " The function is a quadratic polynomial from x0 to x1, linear over x1 to x2," \
    " and another quadratic polynomial from x2 to x3, with smooth transitions at the joins." \
    " x1 can equal x0, or x2 equal x3, to disable easing at the corresponding end."

    ease_ratio = .5
    y1 = (x1 - x0) / (x3 - x0) * (to_y - from_y) * ease_ratio + from_y
    y2 = (x2 - x3) / (x0 - x3) * (from_y - to_y) * ease_ratio + to_y
    x1p = (x2 - x1) / (y2 - y1) * (x1 - x0) + x0
    x2p = (x1 - x2) / (y1 - y2) * (x2 - x3) + x3
    dy1p = ((x1 - x0) / (x1p - x0)) ** 2 if x1 != x0 else None
    dy2p = ((x2 - x3) / (x2p - x3)) ** 2 if x2 != x3 else None

    @interpolator
    def ease_inout(x) :
        if x < x1 and dy1p != None :
            y = ((x - x0) / (x1p - x0)) ** 2 / dy1p * (y1 - from_y) + from_y
        elif x > x2 and dy2p != None :
            y = ((x - x3) / (x2p - x3)) ** 2 / dy2p * (y2 - to_y) + to_y
        else :
            y = (x - x1) / (x2 - x1) * (y2 - y1) + y1
        #end if
        return \
            y
    #end ease_inout

    return \
        ease_inout
#end ease_inout_interpolator

def piecewise_interpolator(x_vals, interps) :
    "x_vals must be a monotonically-increasing sequence of x-values, defining" \
    " domain segments, and interps must be a tuple of interpolator functions," \
    " one less in length. interps[i] is used for x values in the range" \
    " x_vals[i] .. x_vals[i + 1]. The x value is first normalized to [0 .. 1]" \
    " over this range, and the returned ranges from interpolators after the first one" \
    " are adjusted, each relative to the previous one, to ensure the overall" \
    " interpolation is piecewise continuous."

    @interpolator
    def interpolate(x) :
        y_offset = 0
        i = 0
        while True :
            if i >= len(interps) - 1 or x_vals[i + 1] >= x :
                y = interps[i]((x - x_vals[i]) / (x_vals[i + 1] - x_vals[i])) + y_offset
                break
            #end if
            y_offset += interps[i](1) - interps[i + 1](0)
            i += 1
        #end while
        return y
    #end interpolate

#begin piecewise_interpolator
    assert len(x_vals) >= 2 and len(interps) + 1 == len(x_vals)
    interps = tuple(ensure_interpolator(f) for f in interps)
    return \
        interpolate
#end piecewise_interpolator

def piecewise_linear_interpolator(x_vals, y_vals) :
    "x_vals must be a monotonically-increasing sequence of x-values, defining" \
    " domain segments, and y_vals must be a monotically-increasing sequence of" \
    " the same length of corresponding y-values defining piecewise-linear" \
    " range segments. returns a function that will map an input x value to" \
    " the corresponding y value linearly-interpolated over the appropriate segment."
    assert len(x_vals) >= 2 and len(x_vals) == len(y_vals)
    return \
        piecewise_interpolator \
          (
            x_vals,
            tuple
              (
                linear_interpolator(0, 1, y_vals[i], y_vals[i + 1])
                for i in range(0, x_vals - 1)
              )
          )
#end piecewise_linear_interpolator

def periodic_interpolator(from_x, to_x, interp, offset = 0) :
    "given an existing interpolator defined over the domain [from_x, to_x], returns" \
    " an interpolator which repeats the same function over equal-sized intervals" \
    " before and after the original domain."
    return \
        interpolator \
          (
            lambda x : interp((x - offset) % (to_x - from_x) + from_x)
          )
#end periodic_interpolator

def step_interpolator(x_vals, y_vals) :
    "x_vals must be a tuple of monotonically increasing values, and y_vals a tuple" \
    " with a length one less. returns an interpolator that returns y_vals[i] when" \
    " x_vals[i] ≤ x ≤ x_vals[i + 1]."

    @interpolator
    def step_interpolate(x) :
        i = len(x_vals) - 2
        while x_vals[i] > x :
            i -= 1
        #end while
        return \
            y_vals[i]
    #end step_interpolate

#begin step_interpolator
    assert len(x_vals) >= 2 and len(x_vals) == len(y_vals) + 1
    return \
        step_interpolate
#end step_interpolator

def transform_interpolator(interp, scale, offset) :
    "returns an interpolator which is interp operating on an x-coordinate subjected" \
    " to the specified scale and offset."
    return \
        interpolator(lambda x : interp((x - offset) / scale))
#end transform_interpolator

def matrix_interpolator(*args) :
    "the argument(s) must be a sequence of interpolators returning qahirah.Matrix" \
    " values. The result will be an interpolator that concatenates the matrices that" \
    " they return in sequence at the specified animation time."

    @interpolator
    def concat_matrices(x) :
        result = qah.Matrix.identity()
        for f in args :
            result *= f(x)
        #end for
        return \
            result
    #end concat_matrices

#begin matrix_interpolator
    if len(args) == 1 and type(args[0]) == tuple :
        args = args[0]
    #end if
    args = tuple \
      (
        ensure_interpolator(arg)
        for arg in args
      )
    return \
        concat_matrices
#end matrix_interpolator

def function_interpolator(func, args = None, kwargs = None) :
    "creates an interpolator that applies func to the arguments *args and" \
    " keyword arguments **kwargs at a given time. Any of the arguments may" \
    " be interpolators which will be evaluated at the specified time before" \
    " being passed to the function."

    @interpolator
    def apply_function(x) :
        cur_args = tuple \
          (
            arg(x) for arg in args
          )
        cur_kwargs = dict \
          (
            (k, kwargs[k](x))
            for k in kwargs
          )
        return \
            func(*cur_args, **cur_kwargs)
    #end apply_function

#begin function_interpolator
    if args != None :
        args = tuple \
          (
            ensure_interpolator(arg)
            for arg in args
          )
    else :
        args = ()
    #end if
    if kwargs != None :
        kwargs = dict \
          (
            (k, ensure_interpolator(kwargs[k]))
            for k in kwargs
          )
    else :
        kwargs = {}
    #end if
    return \
        apply_function
#end function_interpolator

def hsva_to_colour_interpolator(h, s, v, a) :
    "given h, s, v, a interpolators or constant values, returns an interpolator that" \
    " converts the interpolated values to a qahirah.Colour. Handy because animating" \
    " in HSV space rather than RGB usually gives more useful effects."
    return \
        function_interpolator \
          (
            func = lambda h, s, v, a : qah.Colour.from_hsva((h, s, v, a)),
            args = (h, s, v, a)
          )
#end hsva_to_colour_interpolator

def hlsa_to_colour_interpolator(h, l, s, a) :
    "given h, l, s, a interpolators or constant values, returns an interpolator that" \
    " converts the interpolated values to a qahirah.Colour. Handy because animating" \
    " in HLS space rather than RGB usually gives more useful effects."
    return \
        function_interpolator \
          (
            func = lambda h, l, s, a : qah.Colour.from_hlsa((h, l, s, a)),
            args = (h, l, s, a)
          )
#end hlsa_to_colour_interpolator

#+
# Draw procedures
#-

def null_draw(g, x) :
    "a draw procedure which does nothing."
    pass
#end null_draw

def make_draw(*draw_settings) :
    "draw_settings must be a tuple of 2-tuples; in each 2-tuple, the first element is" \
    " a qahirah.Context method name, and the second element is a tuple of arguments to that" \
    " method, or an interpolator function returning such a tuple. If the second element is" \
    " a tuple, then each element is either a corresponding argument value, or an interpolator" \
    " that evaluates to such an argument value. This function returns a draw procedure" \
    " that applies the specified settings to a given Cairo context at the specified time."

    def apply_settings(g, x) :
        for method, interp in draw_settings :
            if is_interpolator(interp) :
                args = interp(x)
            else : # assume tuple
                args = tuple \
                  (
                    ensure_interpolator(arg)(x)
                    for arg in interp
                  )
            #end if
            getattr(g, method)(*args)
        #end for
    #end apply_settings

#begin make_draw
    if (
            len(draw_settings) == 1
        and
            type(draw_settings[0]) == tuple
        and
                (
                    len(draw_settings[0]) != 2
                or
                    len(draw_settings[0]) == 2 and type(draw_settings[0][0]) != str
                )
    ) :
        draw_settings = draw_settings[0]
    #end if
    return \
        apply_settings
#end make_draw

def draw_overlay(*draw_procs) :
    "given a sequence of draw procedures, returns a draw procedure that invokes" \
    " them one on top of the other. The Cairo context is saved/restored around each one."

    def apply_overlay(g, x) :
        for proc in draw_procs :
            g.save()
            proc(g, x)
            g.restore()
        #end for
    #end apply_overlay

#begin draw_overlay
    if len(draw_procs) == 1 and type(draw_procs[0]) == tuple :
        draw_procs = draw_procs[0]
    #end if
    return \
        apply_overlay
#end draw_overlay

def draw_compose(*draw_procs) :
    "given a sequence of draw procedures, returns a draw procedure that invokes" \
    " them one after the other. Unlike draw_overlay, the Cairo context is NOT" \
    " saved/restored around each one."

    def apply_compose(g, x) :
        for proc in draw_procs :
            proc(g, x)
        #end for
    #end apply_compose

#begin draw_compose
    if len(draw_procs) == 1 and type(draw_procs[0]) == tuple :
        draw_procs = draw_procs[0]
    #end if
    return \
        apply_compose
#end draw_compose

def draw_sequence(x_vals, draws) :
    "given a sequence of x values x_vals, and a sequence of draw procedures draws" \
    " such that len(draws) = len(x_vals) + 1, returns a draw procedure which will" \
    " invoke draws[0] during the time before x_vals[0], draws[-1] during the time" \
    " after x_vals[-1], and in-between elements of draws during the corresponding" \
    " intervals between consecutive elements of x_vals. You can use null_draw if you" \
    " don’t want drawing to happen during a particular range of times."

    def select_from_sequence(g, x) :
        i = len(x_vals)
        while True :
            if i == 0 :
                draw = draws[0]
                break
            #end if
            if x >= x_vals[i - 1] :
                draw = draws[i]
                break
            #end if
            i -= 1
        #end while
        draw(g, x)
    #end select_from_sequence

#begin draw_sequence
    assert len(draws) != 0 and len(x_vals) + 1 == len(draws)
    return \
        select_from_sequence
#end draw_sequence

def retime_draw(draw, interp) :
    "returns a draw procedure which invokes draw with the time transformed through interp."
    def apply_draw(g, x) :
        draw(g, interp(x))
    #end apply_draw
    return \
        apply_draw
#end retime_draw

def transform_draw(draw, scale, offset) :
    "returns a draw procedure which is draw operating on an x-coordinate subjected" \
    " to the specified scale and offset."
    return \
        retime_draw(draw, lambda x : (x - offset) / scale)
#end transform_draw

#+
# Higher-level useful stuff
#-

def draw_curve(g, f, closed, nr_steps, start = 0, end = 1) :
    "g is a qahirah.Context, f is a function over [0, 1) returning" \
    " (a value compatible with) a qahirah.Vector of (x, y) coordinates," \
    " defining the curve to draw, and nr_steps is the number of straight-" \
    "line segments to approximate the curve. start and end are the relative" \
    " start and end fractions, in [0, 1], of the actual part of the curve to" \
    " draw; if omitted, they default to the entire curve. end can be less" \
    " than start, to wrap around the curve. If closed, then the end and start" \
    " points will be joined by an additional segment. The path will be" \
    " stroked with the current settings in g."
    g.new_path()
    if end < start :
        end += 1
    #end if
    start_step = round(start * nr_steps)
    end_step = round(end * nr_steps)
    for i in range(start_step, end_step) :
        g.line_to(f((i % nr_steps) / nr_steps))
    #end for
    if closed and start_step % nr_steps == end_step % nr_steps :
        g.close_path()
    #end if
    g.stroke()
#end draw_curve

def render_anim \
  (
    dimensions, # qahirah.Vector
    start_time,
    end_time,
    frame_rate,
    draw_frame, # draw procedure
    overall_presetup, # called to do once-off setup of qahirah Context
    out_dir, # where to write numbered PNG frames
    start_frame_nr # frame number corresponding to time 0
  ) :
    "renders out an animation to a sequence of PNG image files."
    pix = qah.ImageSurface.create(qah.CAIRO.FORMAT_ARGB32, dimensions)
    g = qah.Context.create(pix)
    if overall_presetup != None :
        overall_presetup(g)
    #end if
    from_frame_nr = math.ceil(start_time * frame_rate)
    to_frame_nr = math.ceil(end_time * frame_rate)
    for frame_nr in range(from_frame_nr, to_frame_nr) :
        g.save()
        t = frame_nr / frame_rate
        draw_frame(g, t)
        g.restore()
        pix.flush()
        pix.write_to_png \
          (
            os.path.join(out_dir, "%04d.png" % (frame_nr + start_frame_nr))
          )
    #end for
    return \
        (from_frame_nr, to_frame_nr)
#end render_anim
