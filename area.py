"""Simple module to compute areas of shapes.

Currently provides:
    - calculate_circle_area(radius)

If executed as a script it will prompt for a radius and print the
computed area.
"""

import math


def calculate_circle_area(radius):
    """Return the area of a circle with the given radius.

    Formula: π * r²
    Raises ValueError if radius is negative.
    """
    if radius < 0:
        raise ValueError("Radius cannot be negative")
    return math.pi * radius * radius


if __name__ == "__main__":
    try:
        r = float(input("Enter circle radius: "))
        area = calculate_circle_area(r)
        print(f"Area of circle with radius {r}: {area}")
    except ValueError as err:
        print(f"Error: {err}")
