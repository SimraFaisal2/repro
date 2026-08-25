"""Line reader. Subscripts the value returned by an external streaming
library, assuming it is a list — but it is a generator."""


def first_line(stream):
    return stream[0]
