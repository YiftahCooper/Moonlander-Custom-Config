'use strict';

(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.MoonlanderCommandInstaller = api;
}(this, function () {
  var COMMAND_NAMES = [
    'Moonlander: Smart Title Case',
    'Moonlander: Cycle Case',
    'Moonlander: Transplant Hebrew-English',
  ];

  function isMoonlanderName(name) {
    return COMMAND_NAMES.indexOf(name) !== -1;
  }

  function shortcutText(shortcut) {
    return shortcut === undefined || shortcut === null
      ? ''
      : String(shortcut).trim().toLowerCase();
  }

  function shortcutTexts(command) {
    var shortcuts = command.globalShortcuts;
    if (shortcuts === undefined || shortcuts === null) {
      shortcuts = command.globalShortcut === undefined ? [] : [command.globalShortcut];
    } else if (!Array.isArray(shortcuts)) {
      shortcuts = [shortcuts];
    }
    return shortcuts.map(shortcutText).filter(function (shortcut) { return shortcut !== ''; });
  }

  function cloneCommand(command) {
    var clone = {};
    Object.keys(command).forEach(function (key) { clone[key] = command[key]; });
    return clone;
  }

  function quoteForCopyQScript(value) {
    return String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  }

  function commandScript(installDir, helperPath, transformName, options) {
    var safeInstallDir = quoteForCopyQScript(installDir);
    var safeHelperPath = quoteForCopyQScript(helperPath);
    return [
      'copyq:',
      "source('" + safeInstallDir + "/transformations.js');",
      "source('" + safeInstallDir + "/transaction.js');",
      'MoonlanderTransaction.runTransaction(',
      '    MoonlanderTransforms.' + transformName + ',',
      '    ' + options + ',',
      "    MoonlanderTransaction.createCopyQAdapter('" + safeHelperPath + "')",
      ');',
    ].join('\n');
  }

  function createCommands(installDir, helperPath) {
    return [
      {
        name: COMMAND_NAMES[0],
        cmd: commandScript(installDir, helperPath, 'smartTitleCase', '{}'),
        globalShortcuts: ['F13'],
      },
      {
        name: COMMAND_NAMES[1],
        cmd: commandScript(installDir, helperPath, 'cycleCase', '{reselect: true}'),
        globalShortcuts: ['F19'],
      },
      {
        name: COMMAND_NAMES[2],
        cmd: commandScript(installDir, helperPath, 'transplantHebrewEnglish', '{}'),
        globalShortcuts: ['F22'],
      },
    ];
  }

  function validateIncoming(incoming) {
    if (incoming.length !== COMMAND_NAMES.length) {
      throw new Error('Command template must contain exactly three Moonlander commands');
    }
    COMMAND_NAMES.forEach(function (name) {
      var count = incoming.filter(function (command) { return command.name === name; }).length;
      if (count !== 1) {
        throw new Error('Command template must contain exactly one command named ' + name);
      }
    });
  }

  function mergeCommands(existing, incoming, activateShortcuts) {
    validateIncoming(incoming);
    var prepared = incoming.map(function (command) {
      var clone = cloneCommand(command);
      delete clone.globalShortcut;
      if (activateShortcuts) {
        clone.isGlobalShortcut = true;
      } else {
        clone.globalShortcuts = [];
        clone.isGlobalShortcut = false;
      }
      return clone;
    });

    if (activateShortcuts) {
      prepared.forEach(function (desired) {
        shortcutTexts(desired).forEach(function (wanted) {
          existing.forEach(function (current) {
            if (!isMoonlanderName(current.name)
                && shortcutTexts(current).indexOf(wanted) !== -1) {
              throw new Error(
                wanted.toUpperCase() + ' is already assigned to CopyQ command ' + current.name,
              );
            }
          });
        });
      });
    }

    return existing.filter(function (command) {
      return !isMoonlanderName(command.name);
    }).concat(prepared);
  }

  function verifyInstalledShortcuts(installed, activateShortcuts) {
    var expected = createCommands('', '');
    expected.forEach(function (wanted) {
      var matches = installed.filter(function (command) { return command.name === wanted.name; });
      var wantedShortcuts = activateShortcuts ? shortcutTexts(wanted) : [];
      if (matches.length !== 1
          || JSON.stringify(shortcutTexts(matches[0])) !== JSON.stringify(wantedShortcuts)
          || Boolean(matches[0].isGlobalShortcut) !== Boolean(activateShortcuts)) {
        throw new Error('CopyQ shortcut verification failed for ' + wanted.name);
      }
    });
  }

  function install(installDir, helperPath, activateShortcuts) {
    var incoming = createCommands(installDir, helperPath);
    var merged = mergeCommands(commands(), incoming, activateShortcuts);
    setCommands(merged);
    verifyInstalledShortcuts(commands(), activateShortcuts);
    return merged.length;
  }

  return {
    COMMAND_NAMES: COMMAND_NAMES,
    createCommands: createCommands,
    mergeCommands: mergeCommands,
    verifyInstalledShortcuts: verifyInstalledShortcuts,
    install: install,
  };
}));
