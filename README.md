# Custom QMK Build for ZSA Moonlander (Clever Injection Method)

This repository allows you to sync your Oryx layout with custom QMK code **without merge conflicts**.

## How it works (The Clever Bit)

Instead of maintaining a modified `keymap.c` and fighting git merge conflicts every time Oryx updates:
1.  We maintain our custom code in `custom_qmk/custom_code.c`.
2.  The workflow downloads the *fresh* Oryx source code.
3.  It **injects** our custom code into the Oryx keymap on-the-fly during the build.
    *   It renames Oryx's `process_record_user` to `process_record_user_oryx`.
    *   It adds a wrapper `process_record_user` that calls YOUR code first.

## How to use

1.  **Add Custom Logic**:
    *   Edit `custom_qmk/custom_code.c` in this repository.
    *   Add your macros, key overrides, or LED logic there.
2.  **Run the Workflow**:
    *   Go to **Actions** -> **Fetch and build layout**.
    *   Run on branch **`main`**.
3.  **Download Firmware**:
    *   Get the `.bin` file from the run artifacts.
4.  **Optional: Windows Language Sync (Windhawk)**:
    *   Follow `docs/windhawk-language-sync.md` to sync OS language state to keyboard RGB.

## File Structure

*   `custom_qmk/custom_code.c`: **EDIT THIS FILE.** This is where your code lives.
*   `scripts/patch_keymap.py`: The script that performs the injection.
*   `keymap.c` (in artifacts): Generated automatically. Do not edit.

## Why this is better
*   **No Conflicts**: You never edit the generated Oryx file directly.
*   **Clean History**: Your repo only tracks your custom code, not the thousands of lines of Oryx generated code.
*   **Safe**: If Oryx updates their code structure, the patch script might fail (safe fail), but you won't silently lose logic in a bad merge.

## MIDI layer (Layer 2)

Oryx has no native MIDI keycode support, so the MIDI keys are injected during the
build. `scripts/patch_keymap.py` overwrites the placeholder keys on **Layer 2**
(`keymaps[2]`) with real QMK MIDI keycodes and enables MIDI in the build.

### Note map

Melody (Row 2, the natural/white keys):

| Hand | Keys | Notes |
|---|---|---|
| Left  | k20–k26 | `C3 D3 E3 F3 G3 A3 B3` |
| Right | k27–k2d | `C4 D4 E4 F4 G4 A4 B4` |

Sharps/flats (Row 1, biased right so each accidental sits above the next natural):

| Hand | Notes |
|---|---|
| Left (octave 3)  | `C#3 D#3  F#3 G#3 A#3` |
| Right (octave 4) | `Db4 Eb4  Gb4 Ab4 Bb4` (enharmonic = `C#4 D#4 F#4 G#4 A#4`) |

Bass (Rows 3–4, left hand only; F#2 is omitted to fit 11 keys):

| Row | Keys | Notes |
|---|---|---|
| Row 3 (BASS1–6)  | k30–k35 | `C2 C#2 D2 D#2 E2 F2` |
| Row 4 (BASS7–11) | k40–k44 | `G2 G#2 A2 A#2 B2` |

### Bass shifter (thumb cluster)

The two purple-lit left thumb keys are **BASS_up** (k51) and **BASS_down** (k52).
Each tap transposes **all bass notes by ±1 semitone** (a free transpose across
octaves, not a wrap within one octave). The offset is clamped to `-24..+24`
semitones so the host never receives an out-of-range MIDI note.

Implementation detail: the firmware intercepts bass keys by **MIDI keycode range**
(`MI_C2 .. MI_B2`), not by matrix position. Melody keys live in a higher keycode
range (`MI_C3 .. MI_B4`) and are never affected by the shifter. On press, the
shifter forwards a transposed note keycode to QMK's `process_midi()`, which emits
the real MIDI note. Each held key snapshots the exact (shifted) note keycode it
sounded, so the matching note-off forwards the same keycode even if the offset
changes mid-hold (no stuck notes).

> Note on pitch: under QMK MIDI the keycode octave is **relative** to the global
> `midi_config.octave` (default puts `MI_C` at note 48 / C3). The keycode names
> here describe the note *relationships*; absolute pitch follows the global octave.

### Build requirements

This project uses **Advanced MIDI** (`MIDI_ADVANCED`), not Basic MIDI. Advanced
is required because only `MIDI_ADVANCED` routes note keycodes through
`process_midi()`, which decodes the note **by keycode value** and emits real
note-on/off — this is what lets the per-key bass shifter sound a transposed note.
(Basic MIDI instead routes notes through `process_music()`, which needs MIDI mode
toggled on and derives notes from matrix position, ignoring the note keycode.)

Two settings are needed, both injected automatically by `patch_keymap.py`:
*   `MIDI_ENABLE = yes` in `rules.mk`
*   `#define MIDI_ADVANCED` in `config.h`

## Windhawk language sync (Windows)

The `host_tools/windhawk` mod syncs the Windows input-language state to the
keyboard RGB indicator over RAW HID, and maps function keys to text helpers:

*   **F18** – language-switch shortcut (default Win+Space).
*   **F22** – wrong-language text fixer (flips Hebrew/English by physical key
    position using the kbdhebl3 layout).
*   **F19** – case cycler (lower → UPPER → Title → lower).

> Map **F22** and **F19** to dedicated keys in Oryx. Do **not** reuse F18, F21,
> or F23 — those scancodes are already emitted by the base keymap, so a global
> hotkey on them would fire on normal key presses. F19 and F22 are unused and
> safe.

See `docs/windhawk-language-sync.md` for setup.
