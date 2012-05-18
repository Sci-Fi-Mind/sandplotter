#!/usr/bin/python
# -*- coding: utf-8 -*-
"""# piclang: A Python EDSL for making paths of interesting shapes. #

Nick Johnson and Kragen Javier Sitaker
<https://gist.github.com/2555227>

This is a simple calculus for easily composing interesting 2-D
parametric curves.  There are three fundamental curves, called
`circle`, `line`, and constant; everything else is built up from these
curves by means of seven primitive combining operations: `+`, `*`,
`**`, `//`, `rotate`, `reverse`, and `concat`.  There’s also a derived
combining operation called `boustro`.

A 2-D parametric curve is a function from time to ordered pairs: that
is, you give it a time, and it gives you a point at that time.  In
this program, time always proceeds from 0 to 1.

## Primitive curves ##

`circle` traces out the unit circle once during this time, starting
and ending at (0, 1).  XXX we should probably fix that.

`line` traces out a line from (0, 0) to (1, 1).

And the constant “curve” always has the same value, which can be any
value.  Constant numbers and ordered pairs are automatically coerced
to constant curves.

## Combining operations ##

The combining operations can be divided into operations that combine
two curves and operations that modify a single curve.

### Operations that combine two curves ###

`+` combines two curves by adding their coordinates pointwise; that is
to say, it translates one curve along the other.  Because it’s
commutative, which curve is the one being translated depends on your
point of view.  For example, `circle + (1, 0)` gives you a radius-1
circle centered at (1, 0) instead of (0, 0), and `circle + line` gives
you a curve that looks kind of like a lowercase “e”, starting at (0,
1) and ending up at (1, 2).  It’s also associative.

`*` combines two curves by *multiplying* their coordinates pointwise;
that is to say, it uses one curve to *nonuniformly* scale the other.
(Again, it’s commutative, so which one is being scaled depends on your
point of view.)  For example, `circle * 0.5` gives you a circle of
radius 0.5, and `circle * line` gives you a one-turn spiral, as the
radius of the circle is smoothly increased from 0 to 1 as it loops
around.  It’s also associative, and it distributes over `+`, so `x *
(y + z)` is the same curve as `x*y + x*z`, if `x` is a curve.

With `+` and `*`, you can use constant functions to translate and
scale `line` so that it makes a line between two arbitrary points.
For example, `line * (2, 3) + (4, 5)` gives you a line from (4, 5) to
(6, 8).  Similarly, you can get a circle around an arbitrary point of
an arbitrary radius with `circle * r + (x, y)`.

`*` allows you to use `line` to do general linear interpolation, and
also to extract individual sinusoids from `circle`, either by
multiplying by a constant, as in `circle * (1, 0)`, or as `circle *
circle`.

`rotate` combines two curves by using one to rotate and *uniformly*
scale the other.  (Again, it’s commutative, so you can think of either
curve as providing the rotation and scale for the other.)  Rotating a
curve by the unit circle `circle` will cause it to rotate one full
revolution while being scaled by 1 (that is, not scaled).  For
example, `rotate(circle, line)` rotates the line one full revolution
as it goes from 0 to 1, producing a rotated version of the same spiral
as `circle * line`.  If you remember elementary school, `rotate` is
just multiplication of complex numbers.  As such, it’s also
associative, and distributes over `+`.

With `rotate`, `+`, `*`, `circle`, and constants, you can get an
ellipse of any shape and orientation at any location.  Using `*`, `+`,
and `rotate` with `line` and constants to construct arbitrary
polynomial parametric curves is almost certainly possible.

Finally, `concat` concatenates two curves, running each one in half
the time.  It is neither associative nor commutative.  Since all of
the above operations run pointwise without affecting the flow of time,
they all distribute over `concat`, `concat` will introduce a
discontinuity at t=0.5 unless the first curve ends where the second
curve begins.

With `concat`, `line`, `+`, `*`, and constants, you can describe
arbitrary line drawings.

### Operations that modify a single curve ###

`**`: For some curve `c` and some number `n`, `c**n` repeats `c` over
and over again, `n` times, by speeding up and repeating the flow of
time.  For example, `circle ** 10 * line` gives you a spiral that
rotates 10 times instead of just once.  `n` can be fractional;
`circle**0.5 is a half-circle.  If the curve doesn’t end where it
begins, `**` introduces floor(n)-1 discontinuities.

Arguably we shouldn’t have called it `**`, because `circle * circle`
is very different from `circle**2`.

`//` discretizes the flow of time: `c//n` evaluates to only floor(n)
distinct values.  When t is a multiple of 1/n, it evaluates to the
same thing as `c`, but then it retains that same value until the next
multiple of 1/n.  For example, `circle * line ** 5` produces five
spirals, but `circle // 5 * line ** 5` produces five straight spokes.
`//` generates floor(n)-1 discontinuities except when applied to
functions that have the same value at more than one of those points.

`reverse` reverses the flow of time.  So far, this is primarily useful
for the `boustro` function, where it allows you to repeat without
introducing discontinuities, and for anguished commentary on the
ultimate emptiness of the pursuit of knowledge.  For example,
`concat(line, reverse(line)) * (0, 1) + line * (1, 0)` is a letter V.

`boustro(curve, times)` is like `curve**times` except that every other
iteration of the curve is time-reversed, so it doesn’t introduce any
discontinuities.

## BUGS ##

We still draw spurious lines between points that are separated by
discontinuities, which sometimes introduces spurious asymmetries in
the image.

We don’t yet adjust sampling density to avoid aliasing problems and
jaggies on complicated curves.

There is not yet a way to see changes in your curve as you edit the
formula.

"""

import inspect
import math
import numbers
import readline
try:
  from PIL import Image, ImageDraw
except ImportError:
  import Image, ImageDraw

class Curve(object):
  @classmethod
  def wrap(cls, o):
    if isinstance(o, Curve):
      return o
    if callable(o):
      return FunctionCurve(o)
    if isinstance(o, numbers.Number):
      return cls.wrap((o, o))
    if isinstance(o, tuple) and len(o) == 2:
      return constant(o)
    raise TypeError("Expected function, number, or 2-tuple, got %r, a %r" % (o, type(o)))

  def __add__(self, other):
    return translate(self, other)

  def __mul__(self, other):
    return scale(self, other)

  def __pow__(self, times):
    return repeat(self, times)

  def __floordiv__(self, steps):
    return step(self, steps)


class FunctionCurve(Curve):
  def __init__(self, func):
    self.func = func

  def __call__(self, t):
    return self.func(t)


class TwoArgCurve(Curve):
  def __init__(self, a, b):
    self.a = Curve.wrap(a)
    self.b = Curve.wrap(b)

  def __call__(self, t):
    return self.invoke(self.a(t), self.b(t))

  
def constant(val):
  return FunctionCurve(lambda t: val)


class translate(TwoArgCurve):
  def invoke(self, (ax, ay), (bx, by)):
    return (ax + bx, ay + by)


class scale(TwoArgCurve):
  def invoke(self, (ax, ay), (bx, by)):
    return (ax * bx, ay * by)


class rotate(TwoArgCurve):
  def invoke(self, (ax, ay), (bx, by)):
    return (ax * bx - ay * by, ay * bx + ax * by)


class reverse(Curve):
  def __init__(self, func):
    self.func = func

  def __call__(self, t):
    return self.func(1 - t)


class concat(Curve):
  def __init__(self, a, b):
    self.a = Curve.wrap(a)
    self.b = Curve.wrap(b)

  def __call__(self, t):
    if t < 0.5:
      return self.a(t * 2)
    else:
      return self.b(t * 2 - 1)


class repeat(Curve):
  def __init__(self, func, times):
    self.func = func
    self.times = times

  def __call__(self, t):
    return self.func((t * self.times) % 1)


class step(Curve):
  def __init__(self, func, steps):
    self.func =func
    self.steps = steps

  def __call__(self, t):
    return self.func(math.floor(t * self.steps) / self.steps)


@FunctionCurve
def circle(t):
  theta = 2 * math.pi * t
  return (math.sin(theta), math.cos(theta))


@FunctionCurve
def line(t):
  return (t, t)


def boustro(func, times):
    return repeat(concat(func, reverse(func)), times/2.0)


def interpolate(f, points):
    return [f(x/float(points)) for x in range(points)]


def render(f, points=1000):
    size = 800
    im = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(im)
    draw.line(interpolate(f * (size/2) + size/2, points), fill=(255,255,255))
    im.show()

class PicStack(object):
    def __init__(self):
        self._stack = []
        self._stackptr = 0 # Points to the first index that's not in the stack
    
    def _popone(self):
        if not self._stack:
            return 0
        self._stackptr -= 1
        if self._stackptr < 0:
            self._stackptr = min(len(self._stack), 8) - 1
        return self._stack[self._stackptr]
    
    def pop(self, num=1):
        return [self._popone() for i in range(num)]

    def push(self, elt):
        if self._stackptr < len(self._stack):
            self._stack[self._stackptr] = elt
        else:
            self._stack.append(elt)
        self._stackptr += 1


def stackparse(expr):
    """Parses a stack-based representation of a curve expression, returning the expression tree."""
    stack = PicStack()
    for token in expr:
        if token is circle or token is line:
            stack.push(token)
        elif isinstance(token, (int, float, tuple)):
            stack.push(token)
        elif callable(token):
            if inspect.isclass(token):
                argcount = len(inspect.getargspec(token.__init__)[0]) - 1
            else:
                argcount = len(inspect.getargspec(token)[0])
            stack.push(token(*stack.pop(argcount)))
    return stack.pop()[0]


repl_doc = """
Available primitives are circle, line, reverse, concat, boustro,
rotate, numbers, 2-tuples of numbers, +, *, //, and **.

Add negatives rather than subtracting; put constants to the right of
+, *, and **.

Some examples to try:
circle * line
circle * circle**20
rotate(boustro(circle * line, 30), circle//30)
circle**29 * boustro(line, 30)
circle**29 * line**30
rotate(boustro(line, 32), circle ** 5) * 0.7
circle**5 * line * circle**5 * line * circle**5 * line
circle * (1, 0) + line * (0, 1)
circle * ((circle * (1, 0) + rotate(circle, (0, 1)) * (0, 1)) ** 8 + 1.9) * (1/2.8)
circle**20 + line + (-1, -1)
circle**2 * (line * .3 + .1) + circle**50 * (line * .05 + .05)
circle * (0, 1) // 20 * (line * 2 + -1) ** 20 + line * (1, 0)
circle ** 5 * (0, 1) + circle ** 3 * (1, 0)
circle ** 30 * 0.8 + circle ** 61 * 0.2
circle ** 30 * 0.8 + circle ** 61 * (line * 0.5 + 0.2)
rotate((circle * (0.2, 0) + (1, 0)) ** 40, circle) * 0.5
rotate((circle * (0.2, 0) + (1, 0)) ** 400, circle ** 10 * (line + 0.1)) * 0.8

"""

def repl():
    import sys
    print repl_doc,
    while True:
        print u"€",
        try:
            input_line = raw_input()
        except EOFError:
            print
            return

        try:
            formula = eval(input_line)
        except:
            _, exc, _ = sys.exc_info()
            print exc
        else:
            render(formula, 4000)

if __name__ == '__main__':
    repl()
    