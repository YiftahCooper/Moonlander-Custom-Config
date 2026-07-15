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

  function cloneCommand(command) {
    var clone = {};
    Object.keys(command).forEach(function (key) { clone[key] = command[key]; });
    return clone;
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
      if (activateShortcuts) {
        clone.isGlobalShortcut = true;
      } else {
        clone.globalShortcut = '';
        clone.isGlobalShortcut = false;
      }
      return clone;
    });

    if (activateShortcuts) {
      prepared.forEach(function (desired) {
        var wanted = shortcutText(desired.globalShortcut);
        existing.forEach(function (current) {
          if (!isMoonlanderName(current.name)
              && wanted
              && shortcutText(current.globalShortcut) === wanted) {
            throw new Error(
              desired.globalShortcut + ' is already assigned to CopyQ command ' + current.name,
            );
          }
        });
      });
    }

    return existing.filter(function (command) {
      return !isMoonlanderName(command.name);
    }).concat(prepared);
  }

  function install(templatePath, activateShortcuts) {
    var incoming = importCommands(templatePath);
    var merged = mergeCommands(commands(), incoming, activateShortcuts);
    setCommands(merged);
    return merged.length;
  }

  return {
    COMMAND_NAMES: COMMAND_NAMES,
    mergeCommands: mergeCommands,
    install: install,
  };
}));
