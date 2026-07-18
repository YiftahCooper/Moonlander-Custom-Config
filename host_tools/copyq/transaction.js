'use strict';

(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.MoonlanderTransaction = api;
}(this, function () {
  function logFailure(adapter, message) {
    try {
      adapter.log(message);
    } catch (_) {
      // Logging must never turn a contained text-tool failure into a dialog.
    }
  }

  function restoreNow(adapter, snapshot) {
    try {
      adapter.restoreClipboard(snapshot);
    } catch (error) {
      logFailure(adapter, 'Moonlander clipboard restoration failed: ' + error);
    }
  }

  function runTransaction(transform, options, adapter) {
    var settings = options || {};
    var state = adapter.state || { generation: 0, active: null };
    var active = state.active;
    var snapshot;

    if (active && adapter.readText() === active.generatedText) {
      snapshot = active.snapshot;
    } else {
      snapshot = adapter.snapshotClipboard();
    }

    var generation = ++state.generation;
    state.active = null;
    var wasMonitoring = adapter.isMonitoring();
    var monitoringRestored = false;
    var restorationDecided = false;
    var generatedText = null;
    var pasted = false;

    adapter.disableMonitoring();
    try {
      adapter.captureSelection();
      var selectedText = adapter.readText();
      if (!selectedText) {
        restoreNow(adapter, snapshot);
        restorationDecided = true;
        return { status: 'no-selection' };
      }

      generatedText = transform(selectedText);
      if (generatedText === selectedText) {
        restoreNow(adapter, snapshot);
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
