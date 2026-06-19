#!/usr/bin/env python3

import unittest
from collections import deque

import numpy as np

import build_jump_v15


def component_sizes(alpha: np.ndarray) -> list[int]:
    opaque = alpha > 0
    height, width = opaque.shape
    visited = np.zeros_like(opaque, dtype=bool)
    sizes: list[int] = []

    for start_y, start_x in np.argwhere(opaque):
        if visited[start_y, start_x]:
            continue

        size = 0
        queue: deque[tuple[int, int]] = deque(
            [(int(start_y), int(start_x))]
        )
        visited[start_y, start_x] = True

        while queue:
            y, x = queue.popleft()
            size += 1
            for offset_y in (-1, 0, 1):
                for offset_x in (-1, 0, 1):
                    if offset_x == 0 and offset_y == 0:
                        continue
                    next_y = y + offset_y
                    next_x = x + offset_x
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and opaque[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))

        sizes.append(size)

    return sorted(sizes, reverse=True)


class JumpBuildTests(unittest.TestCase):
    def test_generated_frames_have_no_detached_small_components(self) -> None:
        for index, frame in enumerate(build_jump_v15.build_jump_frames()):
            with self.subTest(frame=index):
                alpha = np.asarray(frame.getchannel("A"))
                sizes = component_sizes(alpha)
                self.assertFalse(
                    [size for size in sizes[1:] if size <= 127],
                    sizes,
                )


if __name__ == "__main__":
    unittest.main()
