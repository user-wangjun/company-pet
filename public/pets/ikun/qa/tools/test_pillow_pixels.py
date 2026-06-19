#!/usr/bin/env python3

import unittest

from PIL import Image

from pillow_pixels import flattened_pixels


class PillowPixelCompatibilityTests(unittest.TestCase):
    def test_flattens_rgba_pixels_on_supported_pillow_versions(self) -> None:
        image = Image.new("RGBA", (2, 1))
        image.putdata([(1, 2, 3, 4), (5, 6, 7, 8)])

        self.assertEqual(
            list(flattened_pixels(image)),
            [(1, 2, 3, 4), (5, 6, 7, 8)],
        )


if __name__ == "__main__":
    unittest.main()
