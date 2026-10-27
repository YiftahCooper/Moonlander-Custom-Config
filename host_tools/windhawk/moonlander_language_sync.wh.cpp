// ==WindhawkMod==
// @id              moonlander-language-sync
// @name            Moonlander Language Sync
// @description     Maps F18 to Windows language switching and syncs EN/HE state to QMK RGB over RAW HID.
// @version         2.1.0
// @include         explorer.exe
// @compilerOptions -lsetupapi -lhid
// ==/WindhawkMod==

// ==WindhawkModReadme==
// This mod has two responsibilities:
//
// 1) F18 sends the configured Windows language-switch shortcut.
// 2) The active English/Hebrew input language is sent to QMK over RAW HID:
//    - English -> 0
//    - Hebrew  -> 1
//
// Selected-text actions on F13/F19/F22 are owned by CopyQ. This mod deliberately
// contains no clipboard, case-conversion, transplantation, or reselection code.
//
// Transport uses Oryx's ORYX_STATUS_LED_CONTROL command (0x0A). Firmware reads
// the mirrored boolean from rawhid_state.status_led_control.
// After F18, the predicted opposite EN/HE state is sent immediately. Windows is
// then checked every 10 ms until the actual language is confirmed (or 250 ms
// elapse), and any incorrect prediction is corrected. Validated HID device paths
// are cached for the worker lifetime; failures fall back to full discovery.
// Ordinary background synchronization uses the configurable polling interval.
// ==/WindhawkModReadme==

// ==WindhawkModSettings==
/*
- enableF18Hotkey: true
  $name: Enable F18 language hotkey
  $description: If enabled, F18 sends the configured language shortcut.
- shortcutMode: 1
  $name: F18 shortcut mode
  $description: 0=None, 1=Win+Space, 2=Alt+Shift, 3=Ctrl+Shift.
- pollIntervalMs: 120
  $name: Background poll interval (ms)
  $description: How often to read the current Windows input language outside the brief confirmed fast-poll window after F18.
- onlyMoonlander: true
  $name: Restrict to Moonlander
  $description: If enabled, only ZSA devices with product string containing "Moonlander" are targeted.
- debugLogging: false
  $name: Debug logging
  $description: Enable verbose Windhawk log messages.
*/
// ==/WindhawkModSettings==

#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <hidpi.h>

#include <cstdint>
#include <cwctype>
#include <string>
#include <vector>

namespace {

constexpr UINT kHotkeyIdF18 = 0xA701;
constexpr uint16_t kRawHidUsagePage = 0xFF60;
constexpr uint16_t kRawHidUsage = 0x0061;
constexpr uint8_t kOryxStatusLedControlCommand = 0x0A;
constexpr uint8_t kLanguageSyncEnglish = 0x00;
constexpr uint8_t kLanguageSyncHebrew = 0x01;
constexpr DWORD kRetryWhenNotSentMs = 5000;
constexpr DWORD kFastPollIntervalMs = 10;
constexpr DWORD kFastPollTimeoutMs = 250;

enum ShortcutMode : int {
    ShortcutNone = 0,
    ShortcutWinSpace = 1,
    ShortcutAltShift = 2,
    ShortcutCtrlShift = 3,
};

struct Settings {
    bool enable_f18_hotkey = true;
    int shortcut_mode = ShortcutWinSpace;
    int poll_interval_ms = 120;
    bool only_moonlander = true;
    bool debug_logging = false;
};

Settings g_settings;
HANDLE g_stop_event = nullptr;
HANDLE g_worker_thread = nullptr;

std::wstring to_lower_copy(const wchar_t* text) {
    if (!text) {
        return L"";
    }
    std::wstring lowered(text);
    for (wchar_t& ch : lowered) {
        ch = static_cast<wchar_t>(towlower(ch));
    }
    return lowered;
}

bool contains_case_insensitive(const wchar_t* haystack, const wchar_t* needle) {
    if (!needle || needle[0] == L'\0') {
        return true;
    }
    return to_lower_copy(haystack).find(to_lower_copy(needle)) != std::wstring::npos;
}

void load_settings() {
    g_settings.enable_f18_hotkey = Wh_GetIntSetting(L"enableF18Hotkey") != 0;

    int shortcut_mode = Wh_GetIntSetting(L"shortcutMode");
    if (shortcut_mode < ShortcutNone || shortcut_mode > ShortcutCtrlShift) {
        shortcut_mode = ShortcutWinSpace;
    }
    g_settings.shortcut_mode = shortcut_mode;

    int poll_interval_ms = Wh_GetIntSetting(L"pollIntervalMs");
    if (poll_interval_ms < 20 || poll_interval_ms > 2000) {
        poll_interval_ms = 120;
    }
    g_settings.poll_interval_ms = poll_interval_ms;
    g_settings.only_moonlander = Wh_GetIntSetting(L"onlyMoonlander") != 0;
    g_settings.debug_logging = Wh_GetIntSetting(L"debugLogging") != 0;
}

void send_key_event(WORD virtual_key, bool pressed) {
    INPUT input = {};
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = virtual_key;
    if (!pressed) {
        input.ki.dwFlags = KEYEVENTF_KEYUP;
    }
    SendInput(1, &input, sizeof(INPUT));
}

void send_win_space() {
    send_key_event(VK_LWIN, true);
    send_key_event(VK_SPACE, true);
    send_key_event(VK_SPACE, false);
    send_key_event(VK_LWIN, false);
}

void send_modifier_chord(WORD modifier, WORD key) {
    send_key_event(modifier, true);
    send_key_event(key, true);
    send_key_event(key, false);
    send_key_event(modifier, false);
}

void trigger_language_shortcut() {
    switch (g_settings.shortcut_mode) {
        case ShortcutWinSpace:
            send_win_space();
            break;
        case ShortcutAltShift:
            send_modifier_chord(VK_LMENU, VK_LSHIFT);
            break;
        case ShortcutCtrlShift:
            send_modifier_chord(VK_LCONTROL, VK_LSHIFT);
            break;
        case ShortcutNone:
        default:
            break;
    }
}

bool get_active_language_is_hebrew(bool* is_hebrew) {
    if (!is_hebrew) {
        return false;
    }

    HWND foreground_window = GetForegroundWindow();
    DWORD thread_id = foreground_window
        ? GetWindowThreadProcessId(foreground_window, nullptr)
        : 0;
    HKL keyboard_layout = GetKeyboardLayout(thread_id);
    LANGID language_id = LOWORD(reinterpret_cast<UINT_PTR>(keyboard_layout));
    *is_hebrew = PRIMARYLANGID(language_id) == LANG_HEBREW;
    return true;
}

bool device_matches_filters(HANDLE device_handle) {
    wchar_t manufacturer[128] = {};
    wchar_t product[128] = {};
    HidD_GetManufacturerString(device_handle, manufacturer, sizeof(manufacturer));
    HidD_GetProductString(device_handle, product, sizeof(product));

    if (!contains_case_insensitive(manufacturer, L"zsa")) {
        return false;
    }
    return !g_settings.only_moonlander
        || contains_case_insensitive(product, L"moonlander");
}

bool send_language_report_to_device(HANDLE device_handle, bool is_hebrew) {
    PHIDP_PREPARSED_DATA preparsed_data = nullptr;
    if (!HidD_GetPreparsedData(device_handle, &preparsed_data) || !preparsed_data) {
        return false;
    }

    HIDP_CAPS caps = {};
    NTSTATUS caps_status = HidP_GetCaps(preparsed_data, &caps);
    HidD_FreePreparsedData(preparsed_data);
    if (caps_status != HIDP_STATUS_SUCCESS) {
        return false;
    }
    if (caps.UsagePage != kRawHidUsagePage || caps.Usage != kRawHidUsage) {
        return false;
    }

    const ULONG report_length = caps.OutputReportByteLength;
    if (report_length < 4) {
        return false;
    }

    std::vector<uint8_t> report(report_length, 0);
    report[0] = 0x00;
    report[1] = kOryxStatusLedControlCommand;
    report[2] = is_hebrew ? kLanguageSyncHebrew : kLanguageSyncEnglish;

    DWORD written = 0;
    BOOL write_ok = WriteFile(
        device_handle,
        report.data(),
        static_cast<DWORD>(report.size()),
        &written,
        nullptr);
    if (write_ok && written == report.size()) {
        return true;
    }

    return HidD_SetOutputReport(
        device_handle,
        report.data(),
        static_cast<ULONG>(report.size())) == TRUE;
}

HANDLE open_language_device(const wchar_t* device_path) {
    return CreateFileW(
        device_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
}

bool try_send_cached_language_state(
    bool is_hebrew,
    const std::vector<std::wstring>& cached_device_paths) {
    if (cached_device_paths.empty()) {
        return false;
    }

    bool all_sent = true;
    for (const std::wstring& device_path : cached_device_paths) {
        HANDLE device_handle = open_language_device(device_path.c_str());
        if (device_handle == INVALID_HANDLE_VALUE) {
            all_sent = false;
            continue;
        }

        if (!send_language_report_to_device(device_handle, is_hebrew)) {
            all_sent = false;
        }
        CloseHandle(device_handle);
    }
    return all_sent;
}

bool discover_and_send_language_state(
    bool is_hebrew,
    std::vector<std::wstring>& cached_device_paths) {
    GUID hid_guid = {};
    HidD_GetHidGuid(&hid_guid);
    HDEVINFO device_info = SetupDiGetClassDevsW(
        &hid_guid,
        nullptr,
        nullptr,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (device_info == INVALID_HANDLE_VALUE) {
        return false;
    }

    bool any_sent = false;
    std::vector<std::wstring> discovered_device_paths;
    SP_DEVICE_INTERFACE_DATA interface_data = {};
    interface_data.cbSize = sizeof(interface_data);

    for (DWORD index = 0;; ++index) {
        if (!SetupDiEnumDeviceInterfaces(
                device_info,
                nullptr,
                &hid_guid,
                index,
                &interface_data)) {
            break;
        }

        DWORD required_size = 0;
        SetupDiGetDeviceInterfaceDetailW(
            device_info,
            &interface_data,
            nullptr,
            0,
            &required_size,
            nullptr);
        if (required_size == 0) {
            continue;
        }

        std::vector<uint8_t> detail_buffer(required_size, 0);
        auto* detail_data = reinterpret_cast<PSP_DEVICE_INTERFACE_DETAIL_DATA_W>(
            detail_buffer.data());
        detail_data->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
        if (!SetupDiGetDeviceInterfaceDetailW(
                device_info,
                &interface_data,
                detail_data,
                required_size,
                nullptr,
                nullptr)) {
            continue;
        }

        HANDLE device_handle = open_language_device(detail_data->DevicePath);
        if (device_handle == INVALID_HANDLE_VALUE) {
            continue;
        }

        if (device_matches_filters(device_handle)
            && send_language_report_to_device(device_handle, is_hebrew)) {
            any_sent = true;
            discovered_device_paths.push_back(detail_data->DevicePath);
        }
        CloseHandle(device_handle);
    }

    SetupDiDestroyDeviceInfoList(device_info);
    if (any_sent) {
        cached_device_paths.swap(discovered_device_paths);
    } else {
        cached_device_paths.clear();
    }
    return any_sent;
}

bool send_language_state_to_keyboards(
    bool is_hebrew,
    std::vector<std::wstring>& cached_device_paths) {
    if (!cached_device_paths.empty()) {
        if (try_send_cached_language_state(is_hebrew, cached_device_paths)) {
            if (g_settings.debug_logging) {
                Wh_Log(
                    L"Language sync HID cache hit: %lu device(s)",
                    static_cast<unsigned long>(cached_device_paths.size()));
            }
            return true;
        }

        if (g_settings.debug_logging) {
            Wh_Log(L"Language sync HID cache invalidated; rediscovering");
        }
        cached_device_paths.clear();
    }

    bool sent = discover_and_send_language_state(is_hebrew, cached_device_paths);
    if (g_settings.debug_logging) {
        Wh_Log(
            L"Language sync HID discovery: %ls (%lu device(s) cached)",
            sent ? L"sent" : L"not sent",
            static_cast<unsigned long>(cached_device_paths.size()));
    }
    return sent;
}

DWORD WINAPI worker_thread_proc(void*) {
    MSG message = {};
    PeekMessageW(&message, nullptr, WM_USER, WM_USER, PM_NOREMOVE);

    bool f18_hotkey_registered = false;
    if (g_settings.enable_f18_hotkey && g_settings.shortcut_mode != ShortcutNone) {
        f18_hotkey_registered = RegisterHotKey(nullptr, kHotkeyIdF18, MOD_NOREPEAT, VK_F18) == TRUE;
        if (!f18_hotkey_registered && g_settings.debug_logging) {
            Wh_Log(L"RegisterHotKey(VK_F18) failed: %lu", GetLastError());
        }
    }

    std::vector<std::wstring> cached_device_paths;
    bool have_confirmed_state = false;
    bool confirmed_is_hebrew = false;
    bool confirmed_send_succeeded = false;
    DWORD next_unsent_retry_tick = 0;
    DWORD last_poll_tick = 0;
    bool awaiting_language_change = false;
    bool language_before_shortcut_is_hebrew = false;
    bool have_prediction = false;
    bool predicted_is_hebrew = false;
    bool prediction_send_succeeded = false;
    DWORD fast_poll_started_tick = 0;

    while (WaitForSingleObject(g_stop_event, 0) == WAIT_TIMEOUT) {
        bool f18_dispatched_in_this_drain = false;
        while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
            if (message.message == WM_HOTKEY
                && message.wParam == kHotkeyIdF18
                && !f18_dispatched_in_this_drain) {
                f18_dispatched_in_this_drain = true;
                bool have_pre_switch_language =
                    get_active_language_is_hebrew(&language_before_shortcut_is_hebrew);
                fast_poll_started_tick = GetTickCount();
                trigger_language_shortcut();
                awaiting_language_change = have_pre_switch_language;
                have_prediction = false;
                prediction_send_succeeded = false;
                if (have_pre_switch_language) {
                    predicted_is_hebrew = !language_before_shortcut_is_hebrew;
                    have_prediction = true;
                    prediction_send_succeeded =
                        send_language_state_to_keyboards(predicted_is_hebrew, cached_device_paths);
                    if (g_settings.debug_logging) {
                        Wh_Log(
                            L"Language sync optimistic send: %ls (%ls) after %lu ms",
                            predicted_is_hebrew ? L"Hebrew" : L"English",
                            prediction_send_succeeded ? L"sent" : L"not sent",
                            GetTickCount() - fast_poll_started_tick);
                    }
                }
                have_confirmed_state = false;
                confirmed_send_succeeded = false;
                next_unsent_retry_tick = 0;
                last_poll_tick = 0;
            }
        }

        DWORD now = GetTickCount();
        DWORD poll_interval_ms = awaiting_language_change ? kFastPollIntervalMs
                                                          : static_cast<DWORD>(g_settings.poll_interval_ms);
        if (last_poll_tick == 0
            || now - last_poll_tick >= poll_interval_ms) {
            last_poll_tick = now;

            bool is_hebrew = false;
            if (get_active_language_is_hebrew(&is_hebrew)) {
                bool fast_poll_expired = awaiting_language_change
                    && now - fast_poll_started_tick >= kFastPollTimeoutMs;
                bool still_waiting_for_language_change = awaiting_language_change
                    && !fast_poll_expired
                    && is_hebrew == language_before_shortcut_is_hebrew;

                if (!still_waiting_for_language_change) {
                    awaiting_language_change = false;
                    bool state_changed =
                        !have_confirmed_state || is_hebrew != confirmed_is_hebrew;
                    bool should_retry = !state_changed
                        && !confirmed_send_succeeded
                        && (next_unsent_retry_tick == 0 || now >= next_unsent_retry_tick);
                    bool prediction_matches_confirmed_state =
                        have_prediction
                        && prediction_send_succeeded
                        && is_hebrew == predicted_is_hebrew;
                    bool must_send_confirmed_state =
                        (state_changed && !prediction_matches_confirmed_state)
                        || should_retry;
                    if (state_changed || should_retry || have_prediction) {
                        bool sent = prediction_matches_confirmed_state;
                        if (must_send_confirmed_state) {
                            sent = send_language_state_to_keyboards(
                                is_hebrew,
                                cached_device_paths);
                        }

                        confirmed_is_hebrew = is_hebrew;
                        have_confirmed_state = true;
                        confirmed_send_succeeded = sent;
                        next_unsent_retry_tick = sent ? 0 : now + kRetryWhenNotSentMs;

                        if (g_settings.debug_logging) {
                            if (have_prediction) {
                                Wh_Log(
                                    L"Language sync confirmation: %ls after %lu ms (%ls)",
                                    is_hebrew ? L"Hebrew" : L"English",
                                    now - fast_poll_started_tick,
                                    prediction_matches_confirmed_state
                                        ? L"prediction confirmed"
                                        : L"prediction corrected");
                                if (!prediction_matches_confirmed_state) {
                                    Wh_Log(
                                        L"Language sync correction: %ls (%ls)",
                                        is_hebrew ? L"Hebrew" : L"English",
                                        sent ? L"sent" : L"not sent");
                                }
                            } else if (sent) {
                                Wh_Log(
                                    L"Language sync sent: %ls",
                                    is_hebrew ? L"Hebrew" : L"English");
                            } else {
                                Wh_Log(
                                    L"Language sync not sent; retry scheduled in %lu ms",
                                    kRetryWhenNotSentMs);
                            }
                        }

                        have_prediction = false;
                        prediction_send_succeeded = false;
                    }
                }
            }
        }

        Sleep(10);
    }

    if (f18_hotkey_registered) {
        UnregisterHotKey(nullptr, kHotkeyIdF18);
    }
    return 0;
}

bool start_worker() {
    g_stop_event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    if (!g_stop_event) {
        return false;
    }

    g_worker_thread = CreateThread(nullptr, 0, worker_thread_proc, nullptr, 0, nullptr);
    if (!g_worker_thread) {
        CloseHandle(g_stop_event);
        g_stop_event = nullptr;
        return false;
    }
    return true;
}

void stop_worker() {
    if (g_stop_event) {
        SetEvent(g_stop_event);
    }
    if (g_worker_thread) {
        WaitForSingleObject(g_worker_thread, 5000);
        CloseHandle(g_worker_thread);
        g_worker_thread = nullptr;
    }
    if (g_stop_event) {
        CloseHandle(g_stop_event);
        g_stop_event = nullptr;
    }
}

}  // namespace

BOOL Wh_ModInit() {
    load_settings();
    return start_worker() ? TRUE : FALSE;
}

void Wh_ModUninit() {
    stop_worker();
}

void Wh_ModSettingsChanged() {
    stop_worker();
    load_settings();
    start_worker();
}
