'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { createCommands, install, mergeCommands } = require('../install_commands.js');

const desired = [
  { name: 'Moonlander: Smart Title Case', globalShortcut: 'F13' },
  { name: 'Moonlander: Cycle Case', globalShortcut: 'F19' },
  { name: 'Moonlander: Transplant Hebrew-English', globalShortcut: 'F22' },
];

test('staging replaces only exact Moonlander names and removes shortcuts', () => {
  const unrelated = { name: 'Keep me', globalShortcut: 'Ctrl+K' };
  const oldMoonlander = { name: desired[0].name, globalShortcut: 'F14', old: true };
  const result = mergeCommands([unrelated, oldMoonlander], desired, false);

  assert.equal(result.filter((command) => command.name === desired[0].name).length, 1);
  assert.equal(result.find((command) => command.name === 'Keep me'), unrelated);
  assert.deepEqual(
    result.filter((command) => command.name.startsWith('Moonlander:')).map((command) => command.globalShortcut),
    ['', '', ''],
  );
});

test('activation preserves the requested F13 F19 F22 shortcuts', () => {
  const result = mergeCommands([], desired, true);
  assert.deepEqual(result.map((command) => command.globalShortcut), ['F13', 'F19', 'F22']);
});

test('activation rejects a global shortcut owned by an unrelated command', () => {
  assert.throws(
    () => mergeCommands([{ name: 'Unrelated', globalShortcut: 'f19' }], desired, true),
    /F19.*Unrelated/i,
  );
});

test('similarly prefixed unrelated commands are preserved', () => {
  const nearMatch = { name: 'Moonlander: Cycle Case (old)', globalShortcut: '' };
  const result = mergeCommands([nearMatch], desired, false);
  assert.equal(result.includes(nearMatch), true);
});

test('creates all three command objects directly without an INI parser', () => {
  const result = createCommands('C:/Tools/Moonlander', 'C:/Tools/Moonlander/Reselect.exe');

  assert.deepEqual(result.map((command) => command.name), desired.map((command) => command.name));
  assert.deepEqual(result.map((command) => command.globalShortcut), ['F13', 'F19', 'F22']);
  assert.match(result[0].cmd, /smartTitleCase/);
  assert.match(result[1].cmd, /cycleCase/);
  assert.match(result[1].cmd, /\{reselect: true\}/);
  assert.match(result[2].cmd, /transplantHebrewEnglish/);
  result.forEach((command) => {
    assert.match(command.cmd, /^copyq:/);
    assert.match(command.cmd, /C:\/Tools\/Moonlander\/transformations\.js/);
    assert.match(command.cmd, /C:\/Tools\/Moonlander\/Reselect\.exe/);
  });
});

test('installation never calls importCommands', () => {
  const previous = {
    commands: global.commands,
    setCommands: global.setCommands,
    importCommands: global.importCommands,
  };
  let installed;
  global.commands = () => [{ name: 'Keep me', globalShortcut: '' }];
  global.setCommands = (commands) => { installed = commands; };
  global.importCommands = () => { throw new Error('INI parser must not be called'); };

  try {
    install('C:/Tools/Moonlander', 'C:/Tools/Moonlander/Reselect.exe', false);
  } finally {
    global.commands = previous.commands;
    global.setCommands = previous.setCommands;
    global.importCommands = previous.importCommands;
  }

  assert.equal(installed.length, 4);
  assert.equal(installed[0].name, 'Keep me');
});
