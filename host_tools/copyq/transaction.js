'use strict';

(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.MoonlanderTransaction = api;
}(this, function () {
  function runTransaction(transform, options, adapter) {
    var settings = options || {};
    var snapshot = adapter.snapshotClipboard();
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
        adapter.restoreClipboard(snapshot);
        restorationDecided = true;
        return { status: 'no-selection' };
      }

      generatedText = transform(selectedText);
      if (generatedText === selectedText) {
        adapter.restoreClipboard(snapshot);
        restorationDecided = true;
        return { status: 'no-change' };
      }

      adapter.writeText(generatedText);
      adapter.sleep(40);
      adapter.paste();
      pasted = true;

      if (wasMonitoring) {
        adapter.enableMonitoring();
        monitoringRestored = true;
      }

      if (settings.reselect) {
        adapter.sleep(35);
        var exitCode = adapter.reselect(generatedText);
        if (exitCode !== undefined && exitCode !== 0) {
          throw new Error('Moonlander.Reselect failed with exit code ' + exitCode);
        }
      }

      adapter.sleep(250);
      if (adapter.readText() === generatedText) {
        adapter.restoreClipboard(snapshot);
      }
      restorationDecided = true;
      return { status: 'transformed', text: generatedText };
    } finally {
      if (wasMonitoring && !monitoringRestored) {
        adapter.enableMonitoring();
      }
      if (!restorationDecided) {
        if (!pasted || generatedText === null || adapter.readText() === generatedText) {
          adapter.restoreClipboard(snapshot);
        }
      }
    }
  }

  function createCopyQAdapter(helperPath) {
    return {
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
      sleep: function (milliseconds) { sleep(milliseconds); },
      reselect: function (text) {
        var result = execute(helperPath, null, text);
        return result && result.exit_code !== undefined ? result.exit_code : 0;
      },
      restoreClipboard: function (item) { copy(item); },
    };
  }

  return {
    runTransaction: runTransaction,
    createCopyQAdapter: createCopyQAdapter,
  };
}));
