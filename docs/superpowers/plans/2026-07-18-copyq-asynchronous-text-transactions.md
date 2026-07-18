# CopyQ Asynchronous Text Transactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove CopyQ's blocking transaction sleeps while preserving safe clipboard restoration, F19 reselection, and rapid-repeat correctness.

**Architecture:** `runTransaction()` will paste synchronously and delegate delayed reselection and restoration to an injected scheduler backed by CopyQ's `afterMilliseconds()`. A state object stored on CopyQ's documented shared `global` object will assign monotonically increasing generations so stale callbacks cannot affect a newer transaction.

**Tech Stack:** CopyQ 14 JavaScript API, Node.js built-in `node:test`, PowerShell installer.

## Global Constraints

- Keep F13, F19, and F22 ownership and transformations unchanged.
- Preserve every clipboard MIME format and never overwrite a newer user clipboard copy.
- Keep F19 selected with its caret at the right edge; F13 and F22 finish unselected.
- Do not introduce a persistent process, administrator requirement, network access, or new dependency.

---

### Task 1: Specify non-blocking transaction behavior

**Files:**
- Modify: `host_tools/copyq/tests/transaction.test.js`

**Interfaces:**
- Consumes: `runTransaction(transform, options, adapter)`
- Produces: fake adapter contract `schedule(milliseconds, callback)`, `state`, and `log(message)`

- [ ] **Step 1: Replace fake sleeps with a controllable scheduler**

Add a `scheduled` array, shared `state`, and methods:

```javascript
schedule(milliseconds, callback) {
  calls.push(['schedule', milliseconds]);
  scheduled.push({ milliseconds, callback });
},
state: options.state || { generation: 0, active: null },
log(message) { calls.push(['log', message]); },
```

- [ ] **Step 2: Add tests for the critical path and callbacks**

Assert that title/transplant paste without any `sleep`, return before restoration, and schedule restoration at 250 ms. Assert that F19 schedules reselection at 35 ms and restoration at 250 ms. Invoke callbacks explicitly and verify their effects.

- [ ] **Step 3: Add rapid-repeat and error tests**

Run two transactions with the same shared state, invoke the first transaction's callbacks, and assert they are no-ops. Verify the second restoration returns the first transaction's original multi-format snapshot. Make capture and paste throw separately and assert `{status: 'error'}`, monitoring recovery, safe clipboard recovery, and a log call rather than an escaped exception.

- [ ] **Step 4: Run the transaction tests and confirm RED**

Run:

```powershell
node --test host_tools/copyq/tests/transaction.test.js
```

Expected: failures because `runTransaction()` still calls `sleep()` and the adapter has no asynchronous scheduling implementation.

### Task 2: Implement asynchronous scheduling and shared generations

**Files:**
- Modify: `host_tools/copyq/transaction.js`

**Interfaces:**
- Consumes: adapter methods `snapshotClipboard`, `captureSelection`, `writeText`, `paste`, `schedule`, `reselect`, `restoreClipboard`, `log`; adapter property `state`
- Produces: immediate `{status, text?}` transaction results and guarded delayed callbacks

- [ ] **Step 1: Select or preserve the original snapshot**

Before capture, reuse `state.active.snapshot` only when the current clipboard text still equals `state.active.generatedText`; otherwise snapshot the clipboard. Increment `state.generation` and retain the new generation locally.

- [ ] **Step 2: Paste immediately and restore monitoring**

Remove both the 40 ms and 250 ms blocking sleeps. After `writeText(generatedText)`, call `paste()` directly, restore monitoring, and store `{generation, snapshot, generatedText}` in `state.active`.

- [ ] **Step 3: Schedule guarded follow-up work**

For F19, schedule 35 ms reselection; for every transformed result, schedule 250 ms restoration. Each callback first verifies that `state.active.generation === generation`. The restoration callback restores only if clipboard text still equals `generatedText`, then clears the active state.

- [ ] **Step 4: Contain errors**

Catch synchronous capture/paste errors, restore monitoring and the original clipboard when safe, clear this generation, call `adapter.log('Moonlander transaction failed: ' + error)`, and return `{status: 'error'}`. Catch and log helper errors inside the reselection callback without blocking restoration.

- [ ] **Step 5: Back the adapter with CopyQ APIs**

Initialize `global.MoonlanderTransactionState` once, expose it as `adapter.state`, implement `schedule` with `afterMilliseconds(milliseconds, callback)`, remove `sleep`, and implement non-interactive logging with `console.warn(message)`.

- [ ] **Step 6: Run the transaction tests and confirm GREEN**

Run:

```powershell
node --test host_tools/copyq/tests/transaction.test.js
```

Expected: all transaction tests pass.

### Task 3: Verify, document, publish, and activate

**Files:**
- Modify: `host_tools/copyq/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: tested asynchronous transaction implementation
- Produces: installed `%LOCALAPPDATA%\MoonlanderTextTools\transaction.js`

- [ ] **Step 1: Document the non-blocking behavior**

State that CopyQ pastes immediately, schedules F19 reselection at 35 ms, and performs guarded clipboard restoration at 250 ms without blocking CopyQ.

- [ ] **Step 2: Run the full local verification**

```powershell
node --test host_tools/copyq/tests/*.test.js
python -m unittest discover -s tests -v
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'host_tools\copyq\Install-MoonlanderTextTools.ps1'), [ref]$null, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { throw ($errors.Message -join [Environment]::NewLine) }
```

Expected: all Node and Python tests pass and PowerShell reports no parse errors.

- [ ] **Step 3: Commit and publish directly to `main`**

Stage only the transaction, its tests, and synchronized documentation. Commit with `Make CopyQ text transactions non-blocking`. Publish the exact tested blobs directly to `main`, matching the established repository workflow.

- [ ] **Step 4: Reinstall the runtime scripts**

From the worktree, run:

```powershell
.\host_tools\copyq\Install-MoonlanderTextTools.ps1 -ActivateShortcuts
```

Expected: `Installed Moonlander CopyQ commands (active shortcuts).` followed by the backup path.

- [ ] **Step 5: Manual acceptance**

Test F13, F19, and F22 in a normal editor. Confirm immediate text replacement, responsive CopyQ UI, rapid F19 toggling, correct right-edge selection, unchanged CopyQ history, and restoration of the pre-existing clipboard after the final 250 ms delay.
