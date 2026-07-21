# Windhawk Sources

- `moonlander_language_sync.wh.cpp` is the active v2 source. It owns only F18 language switching and EN/HE RGB synchronization.
- `deprecated/moonlander_language_sync_with_text_tools_v1.2.8.deprecated.wh.cpp` is the preserved legacy rollback source. It also owns the old F19/F22 clipboard transformations.

The active source checks Windows every 10 ms for up to 250 ms immediately after F18 and sends RGB state only after the language change is confirmed. Outside that window it uses `pollIntervalMs` (120 ms by default). Firmware interprets English as the unchanged green Oryx base layer and Hebrew as the brown used by Layer 2's black MIDI melody keys on base-colour LEDs only; individually assigned colours, Caps Lock, and higher layers remain under their existing rules.

## Merge and migration rule

Do not overwrite or delete the deprecated v1.2.8 file. Both files must remain in the repository: v2 is the active source, while v1.2.8 provides immediate rollback until the CopyQ and firmware workflow has passed physical acceptance testing.

Never enable both scripts at the same time after CopyQ shortcuts are activated. The deprecated script registers F19 and F22, which would conflict with CopyQ.
