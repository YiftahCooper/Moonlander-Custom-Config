Hey! This repo combines my ZSA Moonlander's online Oryx layout with custom QMK firmware, a custom Windhawk mod, and CopyQ text tools. The Oryx web configurator is limited so I supplemented it with custom code. The additions:

- A 12-note chromatic MIDI piano layer
- Hebrew/English language-aware RGB (requires the accompanying Windhawk mod)
- Smart Title Case and case switching functionality (requires the accompanying CopyQ commands)
- A language correction feature that transplaces Hebrew characters with their English equivalent on a QWERTY layout, and vice versa (requires CopyQ). This fixes the problem of typing an entire English sentence only to discover that Hebrew characters were active.
- Some custom keys and functions; for example, quickly double tapping the right space key outputs ". " just like on my mobile phone

The beauty of this setup is that it uses CI to build everything automatically, merging Oryx and my custom code cleanly and outputting a compiled `.bin` file to flash. Full credit to poulainpi for that functionality: https://github.com/poulainpi/oryx-with-custom-qmk

Open https://configure.zsa.io/moonlander/layouts/3aMQz/latest/0 to see the base layout — most custom keys have peach-colored labels that mark function-key placeholders which get replaced with real behavior by the patch script after the firmware builds.

The rest of this README is AI-generated technical documentation that explains each feature in depth. You can contact me at me@yiftah.com with questions or feedback.

# Custom QMK Firmware for ZSA Moonlander

Advanced MIDI keyboard, language-aware RGB, and Windows text automation — managed through Oryx with zero-merge-conflict CI/CD injection.

## Overview

This repository provides custom QMK firmware for the ZSA Moonlander keyboard, combining:

- **Layer-0 Keymap**: Modified QWERTY with dual-function thumb keys, 3 tap-dances, and F-key placeholders for Windows text automation
- **Language-Aware RGB**: Hebrew/English indicator with Windows sync
- **CopyQ Text Tools**: Clipboard-protected Smart Title Case, case cycling, and Hebrew/English transplantation
- **Windhawk Companion**: Windows language switching and Hebrew/English RGB synchronization
- **CI/CD Pipeline**: Automated Oryx → patch → build → release workflow
- **MIDI Engine (Layer 2)**: A 26-note polyphonic MIDI controller featuring independent melody/bass splits and a dynamic thumb-controlled transpose shifter

The key innovation: Oryx (ZSA's online layout editor) has no native MIDI support. Instead of manually maintaining merge-conflict-prone `keymap.c` files, this project downloads fresh Oryx source in CI, runs `scripts/patch_keymap.py` to inject custom code, builds via Docker, and publishes `.bin` firmware. **No merge conflicts. Only custom code is tracked.**

## <a id="fkey-ref"></a>F-key Availability Quick Reference

Use this table at a glance when adding a new function:

| F-key | Status | Notes |
|---|---|---|
| **F14**, **F15**, **F16**, **F17** | **Free** | No standard OS/browser shortcuts |
| **F20**, **F21**, **F23** | **Free** | No standard OS/browser shortcuts |
| F1–F12 | Reserved | Layer 1 function row (also all have standard OS/browser shortcuts for refresh, search, fullscreen, etc.) |
| F18 | Reserved | Language switch — wired to the left-thumb tap-dance key (k40) and Windhawk |
| F13 | Reserved | CopyQ Smart Title Case — right-space triple tap |
| F19 | Reserved | CopyQ upper/lower toggle — left-space triple tap |
| F22 | Reserved | CopyQ Hebrew/English transplantation — language-key double tap |
| F24 | Reserved | Period-space shortcut (DUAL_FUNC_3, Layer 3 right-hand dual-function key) |

The 7 free keys above (`F14`–`F17`, `F20`, `F21`, `F23`) are neither mapped in firmware nor assigned to these host tools.

## Project Structure

```
Working-Oryx-QMK-Sync/
├── custom_qmk/               ← Canonical custom firmware (custom_code.c)
│   └── custom_code.c         ← MIDI bass shifter, language RGB, tap-dance handlers
├── scripts/                  ← Python patching engine
│   └── patch_keymap.py       ← 11+ deterministic transformations injected into Oryx source
├── host_tools/copyq/         ← CopyQ transformations, protected transaction, installer, tests
├── host_tools/reselect/      ← .NET 10 grapheme-aware reselection helper
├── host_tools/windhawk/      ← Windows Windhawk mod (v2.0.0)
│   ├── moonlander_language_sync.wh.cpp  ← F18 language switching + RGB sync only
│   └── deprecated/           ← Preserved v1.2.8 F19/F22 rollback source; do not delete on merge
├── .github/workflows/        ← CI: fetch Oryx → patch → build → release
│   └── fetch-and-build-layout.yml
├── 3aMQz/                    ← Auto-synced patched layout snapshot (committed by workflow)
│   ├── keymap.c              ← Oryx-generated + patched MIDI layer
│   ├── config.h              ← MIDI_ADVANCED, low-latency settings
│   └── rules.mk              ← MIDI_ENABLE = yes
├── Dockerfile                ← Debian arm-none-eabi QMK build container
└── qmk_firmware/           ← ZSA QMK fork (submodule, fetched at build time)
```

## Features

### 1. Base Layer Keymap (Layer 0)

A modified QWERTY layout with dual-function thumb keys (managed in Oryx, snapshot at `3aMQz/keymap.c`). F18 is owned by Windhawk; F13/F19/F22 selected-text actions are owned by CopyQ.

#### Row 0 (k00–k0d, 14 keys)

| Left half | Right half |
|---|---|
| `ESC` `1` `2` `3` `4` `5` `=` | `MEH_T(PageUp)` `6` `7` `8` `9` `0` `Home` |

- `MEH_T`: Hold activates MeH (Alt+Ctrl+Shift), tap sends the key.

#### Row 1 (k10–k1d, 14 keys)

| Left half | Right half |
|---|---|
| **DUAL_FUNC_0** `Q` `W` `E` `R` `T` `-` | `ALL_T(PgDn)` `Y` `U` `I` `O` `P` `End` |

- `ALL_T`: Hold activates ALL (Ctrl+Alt+Shift+Gui), tap sends the key.
- **DUAL_FUNC_0** (custom override): tap → `DELETE`, hold → `CTRL+DELETE`

#### Row 2 (k20–k2d, 14 keys)

| Left half | Right half |
|---|---|
| **DUAL_FUNC_1** `A` `S` `D` `F` `G` `` ` `` | `TG(1)` `H` `J` `K` `L` `;` `\` |

- `TG(1)`: Momentary toggle to Layer 1.
- **DUAL_FUNC_1** (custom override): tap → `BACKSPACE`, hold → `CTRL+BACKSPACE`

#### Row 3 (k30–k3b, 12 keys)

| Left half | Right half |
|---|---|
| `Shift` `Z` `X` `C` `V` `B` | `N` `M` `,` `.` `Up` `OSL(1)` |

- `OSL(1)`: One-shot Layer 1 (next keypress only).

#### Row 4 (k40–k4b, 12 keys)

| Left half | Right half |
|---|---|
| **DANCE_0** `Gui` `Alt` `[` `]` `MT(RAlt,Tab)` | **DUAL_FUNC_2** `'` `/` `←` `↓` `→` |

- `MT(RAlt, Tab)`: Hold Right Alt, tap Tab.
- **DANCE_0** (language key): single tap → `F18`, hold → `LeftCtrl`, double tap → `F22` transplantation, triple tap → no action
- **DUAL_FUNC_2** (custom override): tap → `ENTER`, hold → `SHIFT+ENTER`

#### Row 5 — Thumb Cluster (k50–k55, 6 keys)

| Left cluster | Right cluster |
|---|---|
| **DANCE_1** `MT(RCtrl,NO)` `MT(Shift+Ctrl,NO)` | `Delete` `Backspace` **DANCE_2** |

- `MT(RCtrl, NO)`: Hold = Right Ctrl; taps do nothing.
- `MT(Shift+Ctrl, NO)`: Hold = Left Shift + Left Ctrl; taps do nothing.
- **DANCE_1** (left space/caps): single tap → `SPACE`, hold → `LEFT_SHIFT`, double tap → `CAPS LOCK`, released triple tap → `F19`
- **DANCE_2** (right space/numdot): single tap → `SPACE`, hold → `SPACE`, double tap → `KP_DOT + SPACE`, released triple tap → `F13`

A held third tap and four-or-more taps intentionally perform no action. Oryx normally generates “repeat the ordinary tap three times” callbacks because its generic tap-dance exporter has no custom semantic for count 3; the patcher disables that fallback for the language dance and both space dances. Only the two space dances receive triple-tap actions.

#### Per-Key Tapping Term Overrides

Three keys have reduced tapping terms to favor tapping over holding during fast typing:

| Key | Override | Effect |
|---|---|---|
| `KC_I` | `TAPPING_TERM - 70` | Faster tap registration on the home-row letter I |
| `KC_DELETE` | `TAPPING_TERM - 120` | Faster tap on the Delete key in the thumb cluster |
| `KC_BSPC` | `TAPPING_TERM - 120` | Faster tap on the Backspace key in the thumb cluster |

### 2. Language-Aware RGB

The left thumb indicator key (k40) lights **blue** (English) or **red** (Hebrew). State is synced from Windows over RAW HID using Oryx's `ORYX_STATUS_LED_CONTROL` command (`0x0A`):
- Param[0] = `0x00` → English
- Param[0] = `0x01` → Hebrew

The indicator only acts on the base layer (Layer 0); other layers use Oryx-configured per-layer colors. This prevents the global language indicator from overriding customized per-key backlighting on higher layers.

In future I will probably change things around so the entire base layer changes from green to a different color when Hebrew is active. I have a hard time seeing the key. 

### 3. Tap-Dance Stabilization

`patch_keymap.py` normalizes tap-dance handlers to fix tapping-term races:
- `SINGLE_HOLD` → `SINGLE_TAP` fallback
- `DOUBLE_SINGLE_TAP` → `DOUBLE_TAP`
- Hold-preference on Space/Shift and F18 language dances
- Signature-detected space-key triple taps for F19/F13, with build failure if any target cannot be identified safely

### 4. Windows Host Tools: CopyQ + Windhawk

Host-key ownership is deliberately split:

| Hotkey | Firmware sources | Owner | Function |
|---|---|---|---|
| **F13** | Right-space triple tap | CopyQ | Smart Title Case; finishes unselected with caret at end |
| **F18** | Language-key single tap | Windhawk | Windows language switch |
| **F19** | Left-space triple tap | CopyQ | `lower ↔ UPPER`; mixed case → `UPPER`; remains selected |
| **F22** | Language-key double tap | CopyQ | Hebrew/English physical-key transplantation; finishes unselected |

Smart Title Case uses the configured small-word list (`a, an, and, as, at, but, by, for, in, nor, of, on, or, per, so, the, to, up, via, vs, yet`), while always capitalizing the first/last lexical word and the first word after a colon or dash. Ordinary words are normalized; acronym detection is intentionally omitted.

Transplantation follows Microsoft `kbdhebl3` physical positions. Direction is chosen by the predominant recognizable alphabet. Lowercase English is mapped to Hebrew, uppercase `A–Z` is preserved, Hebrew maps back to lowercase English, and alphabet ties are no-ops. This preserves the useful pattern where an initial shifted English capital survives while the following accidental lowercase English becomes Hebrew.

CopyQ performs each transformation as a protected, non-blocking transaction: it snapshots every clipboard MIME format, disables history storage, captures and pastes the selection immediately, and restores monitoring. CopyQ then uses `afterMilliseconds()` to reselect F19 output after 35 ms and safely restore the original clipboard after 250 ms only if no newer copy has replaced the generated text. Generation guards make stale callbacks harmless during rapid repeats, so delayed restoration does not freeze the CopyQ UI. The .NET helper used by F19 receives UTF-8 text over standard input, counts Unicode grapheme clusters, and reselects with the caret at the right edge. It has no clipboard, network, administrator, tray, or persistent-process access.

See [`host_tools/copyq/README.md`](host_tools/copyq/README.md) for build, staged installation, activation, acceptance checks, and rollback.

#### <a id="windhawk-setup"></a>Windhawk Setup

The v2 Windhawk source owns only F18 and RGB synchronization. Install or update it from `host_tools/windhawk/moonlander_language_sync.wh.cpp`, then use:

- `enableF18Hotkey = true`
- `shortcutMode = 1` (Win+Space), `2` (Alt+Shift), `3` (Ctrl+Shift), or `0` (none)
- `pollIntervalMs = 120`
- `onlyMoonlander = true`

The previous v1.2.8 implementation is preserved under `host_tools/windhawk/deprecated/` and marked deprecated. It must remain available as the immediate rollback during and after merge; do not enable it simultaneously with active CopyQ F19/F22 shortcuts.

Windhawk sends an Oryx-native RAW HID command to sync Windows language state to keyboard RGB:

- Command: `ORYX_STATUS_LED_CONTROL` (`0x0A`)
- Payload: `param[0] = 0x00` (English), `0x01` (Hebrew)
- Transport: raw HID output report to any ZSA Moonlander device (filtered by manufacturer + product string)
- Firmware reads mirrored state from `rawhid_state.status_led_control` in `custom_qmk/custom_code.c`

The language RGB indicator only responds on Layer 0; MIDI and other layers use Oryx-configured per-layer colors.

Troubleshooting:

- Language switches but RGB does not update: set `debugLogging = true` and check Windhawk's log; temporarily set `onlyMoonlander = false` to test broader HID matching.
- F18 should not trigger Windows language shortcut: set `enableF18Hotkey = false`. Keyboard-side RGB sync still runs.
- Different Windows shortcut preferred: `shortcutMode` = `1` Win+Space (recommended), `2` Alt+Shift, `3` Ctrl+Shift, `0` None.

### 5. Macros (ST_MACRO_0 through ST_MACRO_17)

Layer 1 and Layer 3 carry Unicode and editor macros. Highlights:

| Macros | Purpose |
|---|---|
| `ST_MACRO_0` | Unicode `U+20AC` (Euro €) + Enter |
| `ST_MACRO_1` | Cut (`Ctrl+X`) + type `B` |
| `ST_MACRO_5`–`ST_MACRO_11` | Various `Ctrl+X`/zoom/search shortcuts |
| `ST_MACRO_12`, `ST_MACRO_13` | Alt-code input for `U+002E` (period) |
| `ST_MACRO_14`–`ST_MACRO_17` | Unicode `U+002E` input variants |

These macros include a deliberate 100ms delay (`SS_DELAY(100)`) between keystrokes to ensure OS registration; they can be optimized to 10ms or 0ms in `config.h` if faster output is desired.

### 6. MIDI Layer (Layer 2)


Two octaves of polyphonic MIDI input with split melody/bass and a transpose shifter. Uses **MIDI_ADVANCED** (not MIDI_BASIC) so note keycodes route through `process_midi()` which decodes by keycode value — required for the bass shifter to work correctly.

#### Note Map

**Melody (Row 2, natural/white keys):**

| Hand | Keys | Notes |
|---|---|---|
| Left | k20–k26 | `C3 D3 E3 F3 G3 A3 B3` |
| Right | k27–k2d | `C4 D4 E4 F4 G4 A4 B4` |

**Sharps/flats (Row 1, biased LEFT so each accidental sits directly above the natural it sharpens):**

| Hand | Notes |
|---|---|
| Left (octave 3) | `C#3 D#3  F#3 G#3 A#3` |
| Right (octave 4) | `Db4 Eb4  Gb4 Ab4 Bb4` (enharmonic = `C#4 D#4 F#4 G#4 A#4`) |

**Bass (Rows 3–4 + thumb cluster, left hand only; full chromatic C2–B2):**

| Row | Keys | Notes |
|---|---|---|
| Row 3 (BASS1–6) | k30–k35 | `C2 C#2 D2 D#2 E2 F2` |
| Row 4 (BASS7–11) | k40–k44 | `F#2 G2 G#2 A2 A#2` |
| Row 5 (BASS12) | k50 | `B2` (left thumb cluster, one semitone below BASS1 root) |

#### Bass Shifter (Thumb Cluster)

Three keys share the left thumb cluster on Layer 2: **BASS12** (k50, the 12th chromatic bass note B2), **BASS_up** (k51), and **BASS_down** (k52). The two shifter keys each tap to transpose all bass notes ±1 semitone (free transpose across octaves, clamped −24..+24). Melody keys are in a higher keycode range and are never affected.

**Implementation**: The firmware intercepts bass keys by **MIDI keycode range** (`MI_C2..MI_B2`), not by matrix position. On press, the shifter forwards a transposed note keycode to `process_midi()`, which emits the real MIDI note. Each held key snapshots its shifted note keycode so that a shift change mid-hold cannot strand a stuck note.

> **Note on pitch**: Under QMK MIDI, the keycode octave is **relative** to the global `midi_config.octave` (default puts `MI_C` at note 48 / C3). Keycode names describe note *relationships*; absolute pitch follows the global octave. The firmware sets `midi_config.octave = 1` at init so `MI_C2` sounds as C2 (not C5).

#### Build Requirements (injected automatically by `patch_keymap.py`)

- `MIDI_ENABLE = yes` in `rules.mk`
- `#define MIDI_ADVANCED` in `config.h`
- `DEBOUNCE_TYPE = sym_eager_pk`, `DEBOUNCE = 5`, and `USB_POLLING_INTERVAL_MS = 1` for low-latency MIDI
- `QMK_KEYS_PER_SCAN = 12` for instant polyphonic MIDI chords

## Build Pipeline

Triggered manually via **Actions → Fetch and build layout** (`fetch-and-build-layout.yml`).

**Parameters**: Layout ID (`3aMQz`), geometry (`moonlander/reva`).

**Steps**:
1. Downloads Oryx source → `oryx_source/`
2. Copies `custom_qmk/custom_code.c` → `oryx_source/`
3. Runs `scripts/patch_keymap.py` on `oryx_source/` (11+ transformations)
4. Builds via Docker using ZSA's QMK fork
5. Publishes `.bin` as release artifact
6. Commits patched snapshot to `3aMQz/`

**What the patch script injects**:
- MIDI custom-keycode enum near top of `keymap.c`
- Layer 2 MIDI keycodes (preserving user-added keys like RGB toggles)
- `#define MIDI_ADVANCED` in `config.h`
- `MIDI_ENABLE = yes` in `rules.mk`
- Low-latency settings (`DEBOUNCE_TYPE sym_eager_pk`, `DEBOUNCE 5`, `USB_POLLING_INTERVAL_MS 1`, `QMK_KEYS_PER_SCAN 12`)
- MIDI octave fix (`midi_config.octave = 1` in `keyboard_post_init_user`)
- Tap-dance stabilization patches
- Language RGB indicator hook

## Requirements

- **Hardware**: ZSA Moonlander keyboard
- **Firmware flashing**: [Wally](https://www.zsa.io/wally) or [ZSA Keymapp](https://www.zsa.io/flash)
- **GitHub account**: for Actions (CI builds)
- **Windhawk** (Windows-only, optional): https://windhawk.net/ — install `moonlander_language_sync.wh.cpp`
- **Docker** (for local builds; not needed for CI-only usage)

## Development Workflow

### Making Layout Changes

1. Edit your layout in Oryx (https://configure.zsa.io/)
2. Trigger **Actions → Fetch and build layout** on GitHub
3. Wait ~3-5 minutes for the build
4. `git pull` to get the updated `3aMQz/` folder
5. Flash the `.bin` from the release artifacts

### Adding Custom Firmware Code

1. Edit `custom_qmk/custom_code.c`
2. Commit and push
3. The next workflow run will copy your changes into the build

### Modifying the Patch Script

1. Edit `scripts/patch_keymap.py`
2. Test locally: `python3 scripts/patch_keymap.py 3aMQz`
3. Commit and push
4. The next workflow run will use your updated patch

### Local Testing

```bash
# Clone the ZSA QMK fork
git clone --depth 1 https://github.com/zsa/qmk_firmware.git qmk_firmware
cd qmk_firmware
git checkout firmware25
git submodule update --init --recursive

# Copy your layout
cp -r ../3aMQz keyboards/zsa/moonlander/reva/keymaps/

# Build
make zsa/moonlander/reva:3aMQz
```

## Design Decisions

### Why MIDI_ADVANCED instead of MIDI_BASIC?

Investigation of QMK source confirmed:
- **MIDI_BASIC** routes note keycodes through `process_music()`, which (a) requires MIDI mode toggled ON (`MI_ON`) and (b) derives the note from **matrix position**, ignoring the note keycode entirely. `register_code16()` never emits MIDI.
- **MIDI_ADVANCED** routes note keycodes through `process_midi()`, which decodes the note **by keycode value** (`midi_compute_note`) and tracks note-on/off. No mode toggle needed.

**Decision**: Use MIDI_ADVANCED (strict superset; future-proof). The bass shifter forwards a transposed note keycode to `process_…2460 tokens truncated…, snapshot);
        restorationDecided = true;
        return { status: 'no-change' };
      }

      adapter.writeText(generatedText);
      adapter.paste();
      pasted = true;

      if (wasMonitoring) {
        adapter.enableMonitoring();
        monitoringRestored = true;
      }

      state.active = {
        generation: generation,
        snapshot: snapshot,
        generatedText: generatedText,
      };

      if (settings.reselect) {
        adapter.schedule(35, function () {
          if (!state.active || state.active.generation !== generation) {
            return;
          }
          try {
            var exitCode = adapter.reselect(generatedText);
            if (exitCode !== undefined && exitCode !== 0) {
              logFailure(adapter, 'Moonlander.Reselect failed with exit code ' + exitCode);
            }
          } catch (error) {
            logFailure(adapter, 'Moonlander.Reselect failed: ' + error);
          }
        });
      }

      adapter.schedule(250, function () {
        if (!state.active || state.active.generation !== generation) {
          return;
        }
        try {
          if (adapter.readText() === generatedText) {
            restoreNow(adapter, snapshot);
          }
        } finally {
          if (state.active && state.active.generation === generation) {
            state.active = null;
          }
        }
      });
      restorationDecided = true;
      return { status: 'transformed', text: generatedText };
    } catch (error) {
      if (!pasted || generatedText === null || adapter.readText() === generatedText) {
        restoreNow(adapter, snapshot);
      }
      restorationDecided = true;
      state.active = null;
      logFailure(adapter, 'Moonlander transaction failed: ' + error);
      return { status: 'error' };
    } finally {
      if (wasMonitoring && !monitoringRestored) {
        adapter.enableMonitoring();
      }
      if (!restorationDecided) {
        if (!pasted || generatedText === null || adapter.readText() === generatedText) {
          restoreNow(adapter, snapshot);
        }
      }
    }
  }

  function createCopyQAdapter(helperPath) {
    if (!global.MoonlanderTransactionState) {
      global.MoonlanderTransactionState = { generation: 0, active: null };
    }
    return {
      state: global.MoonlanderTransactionState,
      snapshotClipboard: function () {
        var formats = clipboard('?');
        var item = {};
        for (var i = 0; i < formats.length; ++i) {
          item[formats[i]] = clipboard(formats[i]);
        }
        return item;
      },
      isMonitoring: function () { return monitoring(); },
      disableMonitoring: function () { disable(); },
      enableMonitoring: function () { enable(); },
      captureSelection: function () { copy(); },
      readText: function () { return str(clipboard()); },
      writeText: function (text) { copy(text); },
      paste: function () { paste(); },
      schedule: function (milliseconds, callback) { afterMilliseconds(milliseconds, callback); },
      reselect: function (text) {
        var result = execute(helperPath, null, text);
        return result && result.exit_code !== undefined ? result.exit_code : 0;
      },
      restoreClipboard: function (item) { copy(item); },
      log: function (message) { console.warn(message); },
    };
  }

  return {
    runTransaction: runTransaction,
    createCopyQAdapter: createCopyQAdapter,
  };
}));
