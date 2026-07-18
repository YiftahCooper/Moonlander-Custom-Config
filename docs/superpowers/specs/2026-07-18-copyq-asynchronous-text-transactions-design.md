# CopyQ Asynchronous Text Transactions

## Goal

Make all three Moonlander CopyQ transformations feel immediate and keep CopyQ responsive, without giving up safe restoration of the previous multi-format clipboard.

## Design

- Capture and transform the selected text synchronously.
- Set the transformed clipboard text and paste immediately; do not sleep before pasting.
- Restore CopyQ monitoring immediately after the paste.
- For case cycling, schedule reselection 35 ms after the paste with CopyQ's `afterMilliseconds()` API.
- Schedule guarded clipboard restoration 250 ms after the paste. Restore only when the clipboard still contains the generated text.
- Keep one shared transaction generation in CopyQ's global scope. A newer trigger supersedes callbacks from an older transaction, preventing delayed callbacks from overlapping or restoring stale state.
- Preserve the original clipboard snapshot across a rapid case-cycle sequence so repeated F19 presses eventually restore the clipboard that existed before the first press.

## Error handling

- Selection-copy and paste failures become clean no-ops after restoring monitoring and the original clipboard when safe.
- Log concise failures through CopyQ rather than showing intermittent command-error dialogs.
- A reselection-helper failure is logged and does not prevent the later clipboard restoration.

## Verification

- Unit tests prove there are no blocking sleeps in the transaction path.
- Unit tests control scheduled callbacks and verify delayed reselection and restoration.
- Rapid repeated transactions invalidate older callbacks and preserve the first clipboard snapshot.
- A newer user clipboard copy is never overwritten.
- Existing transformation, installer, firmware, and Windhawk ownership tests remain green.
