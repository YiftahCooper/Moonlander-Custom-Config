#ifndef ORYX_CUSTOM_MOONLANDER_CUSTOM_CODE_C
#define ORYX_CUSTOM_MOONLANDER_CUSTOM_CODE_C

#include "quantum.h"
#ifdef RAW_ENABLE
#include "raw_hid.h"
#endif
#ifdef MIDI_ENABLE
// process_midi() (declared here under MIDI_ADVANCED) decodes MIDI note keycodes
// by value and drives the real MIDI device, including note-on/off tracking.
#include "process_midi.h"

// Fix: QMK's default MIDI octave (4, corresponding to MI_OC2) makes MI_C2 sound
// as C5 instead of C2. Set octave=1 so keycode octaves match sounding octaves:
// MI_C2 -> C2, MI_C3 -> C3, MI_C4 -> C4, etc.
void keyboard_post_init_user(void) {
    midi_config.octave = 1;
}
#endif

// When MIDI is enabled, patch_keymap.py injects `enum user_custom_keycodes`
// (with MIDI_BASS_SHIFT_UP / MIDI_BASS_SHIFT_DOWN) near the TOP of keymap.c so
// the MIDI layer can reference those keycodes before keymaps[] is defined.
// This file is #included at the BOTTOM of keymap.c, so to avoid redefining the
// enum we only declare our own custom keycodes here when MIDI is NOT enabled.
#ifndef MIDI_ENABLE
enum user_custom_keycodes {
    MY_CUSTOM_MACRO = SAFE_RANGE,
};
#endif  // !MIDI_ENABLE

#ifdef MIDI_ADVANCED
// Bass octave/transpose state. Each tap of the thumb shifters moves ALL bass
// notes by +/- 1 semitone (free transpose across octaves), clamped to a sane
// range so the host never receives out-of-range MIDI note numbers.
//
// IMPORTANT: this requires MIDI_ADVANCED (not MIDI_BASIC). Only MIDI_ADVANCED
// exposes process_midi(), which decodes note keycodes by value. We forward a
// transposed note keycode to process_midi() so QMK's MIDI device handles the
// actual note-on/off (and its own per-tone tracking). State is gated on
// MIDI_ADVANCED to match its only use site (avoids unused-variable warnings).
#define MIDI_BASS_SHIFT_MIN (-24)
#define MIDI_BASS_SHIFT_MAX (24)
static int8_t bass_shift_offset = 0;

// Per-key snapshot of the note keycode that was actually sounded on press, so
// the matching release forwards the SAME shifted keycode even if the offset
// changed mid-hold. Keyed by physical matrix position. This prevents stuck
// notes: process_midi() tracks note-on/off by keycode, so press and release
// must use identical keycodes.
static uint16_t bass_active_note[MATRIX_ROWS][MATRIX_COLS];
static bool bass_active[MATRIX_ROWS][MATRIX_COLS];
#endif  // MIDI_ADVANCED

static bool language_is_hebrew = false;
// The language tap-dance key is on matrix [4,0] in this Moonlander layout.
static const uint8_t LANGUAGE_INDICATOR_ROW = 4;
static const uint8_t LANGUAGE_INDICATOR_COL = 0;
static const uint8_t LANGUAGE_ENGLISH_R = 40;
static const uint8_t LANGUAGE_ENGLISH_G = 140;
static const uint8_t LANGUAGE_ENGLISH_B = 255;
static const uint8_t LANGUAGE_HEBREW_R = 255;
static const uint8_t LANGUAGE_HEBREW_G = 0;
static const uint8_t LANGUAGE_HEBREW_B = 0;
static const uint16_t LANGUAGE_TOGGLE_GUARD_MS = 250;

// Suppress duplicate language flips caused by accidental re-triggering/bounce.
static bool language_toggle_guard_armed = false;
static uint16_t language_toggle_timer = 0;

static bool language_toggle_guard_allows_action(void) {
    if (language_toggle_guard_armed && timer_elapsed(language_toggle_timer) < LANGUAGE_TOGGLE_GUARD_MS) {
        return false;
    }
    language_toggle_timer = timer_read();
    language_toggle_guard_armed = true;
    return true;
}

static uint8_t custom_language_indicator_led(void) {
#ifdef RGB_MATRIX_ENABLE
    if (LANGUAGE_INDICATOR_ROW >= MATRIX_ROWS || LANGUAGE_INDICATOR_COL >= MATRIX_COLS) {
        return NO_LED;
    }
    return g_led_config.matrix_co[LANGUAGE_INDICATOR_ROW][LANGUAGE_INDICATOR_COL];
#else
    return NO_LED;
#endif
}

void custom_language_toggled(void) {
    if (!language_toggle_guard_allows_action()) {
        return;
    }
    language_is_hebrew = !language_is_hebrew;
}

void custom_language_toggle(void) {
    if (!language_toggle_guard_allows_action()) {
        return;
    }
    tap_code16(LALT(KC_LEFT_SHIFT));
    language_is_hebrew = !language_is_hebrew;
}

void custom_language_resync(void) {
    if (!language_toggle_guard_allows_action()) {
        return;
    }
    // Force a known baseline: English + default indicator color.
    language_is_hebrew = false;
}

void custom_language_rgb_indicator(void) {
#ifdef RGB_MATRIX_ENABLE
    // Bug 5: only drive the language indicator color on the BASE layer (0).
    // On other layers (e.g. the MIDI layer 2, where this physical key is a bass
    // key) the Oryx-configured per-layer color must win, so we do nothing.
    if (get_highest_layer(layer_state) != 0) {
        return;
    }

    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;
    bool is_hebrew = language_is_hebrew;

#ifdef RAW_ENABLE
    // Oryx owns raw_hid_receive(), so host sync piggybacks on ORYX_STATUS_LED_CONTROL.
    // The host bridge updates rawhid_state.status_led_control to 0 (EN) / 1 (HE).
    is_hebrew = rawhid_state.status_led_control;
#endif

    if (is_hebrew) {
        r = LANGUAGE_HEBREW_R;
        g = LANGUAGE_HEBREW_G;
        b = LANGUAGE_HEBREW_B;
    } else {
        r = LANGUAGE_ENGLISH_R;
        g = LANGUAGE_ENGLISH_G;
        b = LANGUAGE_ENGLISH_B;
    }

    uint8_t led = custom_language_indicator_led();
    if (led != NO_LED) {
        rgb_matrix_set_color(led, r, g, b);
    }
#endif
}

bool process_record_user_custom(uint16_t keycode, keyrecord_t *record) {
#ifdef MIDI_ADVANCED
    // --- Bass thumb shifters: transpose ALL bass notes by +/- 1 semitone. ---
    if (keycode == MIDI_BASS_SHIFT_UP) {
        if (record->event.pressed && bass_shift_offset < MIDI_BASS_SHIFT_MAX) {
            bass_shift_offset++;
        }
        return false;
    }
    if (keycode == MIDI_BASS_SHIFT_DOWN) {
        if (record->event.pressed && bass_shift_offset > MIDI_BASS_SHIFT_MIN) {
            bass_shift_offset--;
        }
        return false;
    }

    // --- Bass notes: intercept by KEYCODE RANGE (octave-2), not matrix row. ---
    // Bass keys carry MI_C2..MI_B2 (a contiguous 12-value range; we populate 11).
    // Melody keys are MI_C3..MI_B4, a higher range that is never intercepted.
    //
    // We forward a TRANSPOSED note keycode to process_midi(), which decodes the
    // note by value and emits the real MIDI note-on/off. We reuse the incoming
    // `record` so the pressed/released state matches; only the keycode changes.
    if (keycode >= MI_C2 && keycode <= MI_B2) {
        uint8_t row = record->event.key.row;
        uint8_t col = record->event.key.col;
        uint16_t shifted;
        if (record->event.pressed) {
            shifted = (uint16_t)((int16_t)keycode + bass_shift_offset);
            if (row < MATRIX_ROWS && col < MATRIX_COLS) {
                bass_active_note[row][col] = shifted;
                bass_active[row][col] = true;
            }
        } else {
            if (row < MATRIX_ROWS && col < MATRIX_COLS && bass_active[row][col]) {
                // Use the snapshot so a mid-hold offset change cannot strand a note.
                shifted = bass_active_note[row][col];
                bass_active[row][col] = false;
            } else {
                shifted = (uint16_t)((int16_t)keycode + bass_shift_offset);
            }
        }
        // Hand the transposed note to QMK's MIDI handler (advanced MIDI).
        process_midi(shifted, record);
        return false;
    }
#endif  // MIDI_ADVANCED

    if (!record->event.pressed) {
        return true;
    }

    // Language toggling is handled in patched tap-dance handlers.
    // Keep this hook available for future custom key logic.
    switch (keycode) {
        default:
            break;
    }
    return true;
}

#endif  // ORYX_CUSTOM_MOONLANDER_CUSTOM_CODE_C
