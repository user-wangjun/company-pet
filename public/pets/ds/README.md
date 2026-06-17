# ds

`ds` is a blue-and-white whale desktop pet built from the user-provided
reference image.

The runtime atlas uses 192x208 cells arranged as 8 columns by 9 rows. The rows
follow the platform animation mapping and `ds`-specific interaction semantics:

- row 0: idle / happy settling, 6 frames
- row 1: drag / jump, 8 frames
- row 2: reserved left-facing movement, 8 frames
- row 3: tickle / affectionate nuzzle, 8 frames
- row 4: crouch alert / spin around, 8 frames
- row 5: hug / curious peek for desktop-icon interaction, 8 frames
- row 6: gnaw / yawn for care reminders, 8 frames
- row 7: chase / active jump movement, 8 frames
- row 8: eat / happy finish, 6 frames

Runtime interaction mapping:

- drag: jump
- single click: affectionate nuzzle
- double click or hover: active jump, then happy finish
- desktop icon interaction: curious peek
- care reminder: yawn
- idle quirks: happy settling, spin around, yawn, curious peek, nuzzle

Pet-specific source and QA notes are kept inside this package.
