# Windhawk Sources

- `moonlander_language_sync.wh.cpp` is the active v2 source. It owns only F18 language switching and EN/HE RGB synchronization.
- `deprecated/moonlander_language_sync_with_text_tools_v1.2.8.deprecated.wh.cpp` is the preserved legacy rollback source. It also owns the old F19/F22 clipboard transformations.

## Merge and migration rule

Do not overwrite or delete the deprecated v1.2.8 file when merging the CopyQ migration. Both files must remain in the repository: v2 is the active source, while v1.2.8 provides immediate rollback until the CopyQ workflow has passed physical acceptance testing.

Never enable both scripts at the same time after CopyQ shortcuts are activated. The deprecated script registers F19 and F22, which would conflict with CopyQ.
