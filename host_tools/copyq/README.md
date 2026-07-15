# Moonlander CopyQ Text Tools

These commands transform selected text without leaving the selection in CopyQ history:

| Command | Shortcut | Result |
|---|---|---|
| `Moonlander: Smart Title Case` | F13 | Smart title rules; caret at end, unselected |
| `Moonlander: Cycle Case` | F19 | lower ↔ UPPER only; selected with caret at right |
| `Moonlander: Transplant Hebrew-English` | F22 | Physical-key transplantation; caret at end, unselected |

Commands require selected text. CopyQ must issue `Ctrl+C` to capture it, so avoid invoking a command without a selection in a terminal where `Ctrl+C` interrupts a process.

## Build and test

From the repository root:

```powershell
node --test host_tools/copyq/tests/*.test.js
dotnet test host_tools/reselect/Moonlander.Reselect.slnx
dotnet publish host_tools/reselect/Moonlander.Reselect/Moonlander.Reselect.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true
```

The published helper is expected at:

```text
host_tools/reselect/Moonlander.Reselect/bin/Release/net10.0-windows/win-x64/publish/Moonlander.Reselect.exe
```

`Moonlander.Reselect.exe` is a short-lived console program. It reads transformed UTF-8 text from standard input, counts grapheme clusters, sends bounded Left and Shift+Right batches, and exits. It does not read or write the clipboard, access the network, request elevation, create a tray icon, or remain running. Exit codes are `0` success, `2` invalid input, and `3` incomplete `SendInput`. `--dry-run` prints the grapheme count without injecting keys.

## Safe cutover

1. Stage the CopyQ commands without shortcuts:

   ```powershell
   .\host_tools\copyq\Install-MoonlanderTextTools.ps1
   ```

   The installer exports the complete current CopyQ command configuration to `%LOCALAPPDATA%\MoonlanderTextTools\backups`, deploys the scripts/helper under `%LOCALAPPDATA%\MoonlanderTextTools`, and replaces only the three exact `Moonlander:` command names. All unrelated commands are preserved.

2. In CopyQ Preferences → Commands, run each staged command manually against selected text. Confirm that CopyQ history count/content does not change and the original rich clipboard returns.

3. Update the active Windhawk mod from `host_tools/windhawk/moonlander_language_sync.wh.cpp`. Version 2 releases F19/F22 and retains only F18 plus RGB synchronization.

   Preserve `host_tools/windhawk/deprecated/moonlander_language_sync_with_text_tools_v1.2.8.deprecated.wh.cpp` during merge. It is the immediate rollback source and must not be overwritten by v2.

4. Activate CopyQ shortcuts:

   ```powershell
   .\host_tools\copyq\Install-MoonlanderTextTools.ps1 -ActivateShortcuts
   ```

   Activation fails if an unrelated CopyQ command already owns F13, F19, or F22. It never silently replaces a collision.

5. Build and flash the firmware. Verify language-key double tap (`F22`) and the two space-key triple taps (`F19`/`F13`).

The installer is idempotent and makes a fresh backup on every run. Use `-WhatIf` to inspect the target without modifying CopyQ.

## Acceptance checks

- `the lord of the rings` becomes `The Lord of the Rings`.
- F19 toggles lowercase ↔ uppercase; mixed case starts at uppercase.
- F19 leaves multiline and emoji-containing text selected with the caret at the right edge.
- `Hello` transplantation preserves `H` and transforms only `ello`.
- Hebrew becomes lowercase English; punctuation follows `kbdhebl3` physical positions.
- Empty, punctuation-only, and alphabet-tie input is unchanged.
- A new clipboard copy made during the delayed restore is not overwritten.
- Twenty repetitions of each space-key triple tap produce one action per triple and preserve single/hold/double behavior.
- The language key taps `F18`, holds Left Ctrl, double taps `F22`, and has no triple-tap action.

## Rollback

Before the firmware cutover, rollback is simply:

1. Disable the three `Moonlander:` CopyQ commands or reinstall them in staged mode.
2. Reinstall/re-enable the previous Windhawk source so it owns F19/F22 again.

If the triple-tap firmware is implicated, flash the previously known-good firmware artifact. Restore a CopyQ backup only if command configuration was damaged; normal rollback does not require replacing unrelated commands.
