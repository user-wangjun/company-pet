#!/usr/bin/env python3

from collections.abc import Iterable

from PIL import Image


def flattened_pixels(image: Image.Image) -> Iterable[object]:
    return image.getdata()
