# ds

`ds` is a blue-and-white whale desktop pet built from the user-provided
reference image.

The runtime atlas uses 192x208 cells arranged as 8 columns by 9 rows. The rows
follow the platform animation mapping:

- row 0: idle, 6 frames
- row 1: drag, 8 frames
- row 2: reserved left-facing movement, 8 frames
- row 3: tickle, 8 frames
- row 4: crouch alert / jump, 8 frames
- row 5: hug, 8 frames
- row 6: gnaw / waiting, 8 frames
- row 7: chase / active movement, 8 frames
- row 8: eat / review, 6 frames

Pet-specific source and QA notes are kept inside this package.
