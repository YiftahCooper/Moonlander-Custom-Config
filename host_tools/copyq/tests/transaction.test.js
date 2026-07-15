'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { runTransaction } = require('../transaction.js');

function fakeAdapter(options = {}) {
  const calls = [];
  let currentText = options.selectionText === undefined ? 'selected text' : options.selectionText;
  let monitoring = options.monitoring === undefined ? true : options.monitoring;
  let restoreRead = 0;
  const snapshot = { 'text/plain': 'old text', 'image/png': '<binary>' };

  return {
    calls,
    snapshot,
    snapshotClipboard() { calls.push('snapshot'); return snapshot; },
    isMonitoring() { calls.push('monitoring'); return monitoring; },
    disableMonitoring() { calls.push('disable'); monitoring = false; },
    enableMonitoring() { calls.push('enable'); monitoring = true; },
    captureSelection() { calls.push('capture'); },
    readText() {
      calls.push('read');
      if (options.newClipboardText !== undefined && restoreRead++ > 0) {
        return options.newClipboardText;
      }
      return currentText;
    },
    writeText(text) { calls.push(['write', text]); currentText = text; },
    paste() { calls.push('paste'); },
    sleep(milliseconds) { calls.push(['sleep', milliseconds]); },
    reselect(text) { calls.push(['reselect', text]); return 0; },
    restoreClipboard(item) { calls.push(['restore', item]); currentText = item['text/plain']; },
  };
}

test('transaction disables history, pastes, and restores every clipboard format', () => {
  const api = fakeAdapter({ selectionText: 'hello' });
  const result = runTransaction((text) => text.toUpperCase(), {}, api);

  assert.deepEqual(result, { status: 'transformed', text: 'HELLO' });
  assert.deepEqual(api.calls, [
    'snapshot', 'monitoring', 'disable', 'capture', 'read',
    ['write', 'HELLO'], ['sleep', 40], 'paste', 'enable',
    ['sleep', 250], 'read', ['restore', api.snapshot],
  ]);
});

test('case transaction sends transformed UTF-8 text to reselection after paste', () => {
  const api = fakeAdapter({ selectionText: 'lower' });
  runTransaction((text) => text.toUpperCase(), { reselect: true }, api);

  assert.ok(api.calls.some((call) => Array.isArray(call)
    && call[0] === 'reselect' && call[1] === 'LOWER'));
  assert.deepEqual(
    api.calls.filter((call) => Array.isArray(call) && call[0] === 'sleep'),
    [['sleep', 40], ['sleep', 35], ['sleep', 250]],
  );
});

test('a newer clipboard change is never overwritten during delayed restoration', () => {
  const api = fakeAdapter({ selectionText: 'hello', newClipboardText: 'new user copy' });
  runTransaction((text) => text.toUpperCase(), {}, api);

  assert.equal(api.calls.some((call) => Array.isArray(call) && call[0] === 'restore'), false);
});

test('originally disabled monitoring remains disabled', () => {
  const api = fakeAdapter({ selectionText: 'hello', monitoring: false });
  runTransaction((text) => text.toUpperCase(), {}, api);

  assert.equal(api.calls.includes('enable'), false);
});

test('empty selection aborts without pasting and restores the clipboard', () => {
  const api = fakeAdapter({ selectionText: '' });
  const result = runTransaction((text) => text.toUpperCase(), {}, api);

  assert.deepEqual(result, { status: 'no-selection' });
  assert.equal(api.calls.includes('paste'), false);
  assert.ok(api.calls.some((call) => Array.isArray(call) && call[0] === 'restore'));
});

test('a no-op transform restores clipboard without pasting', () => {
  const api = fakeAdapter({ selectionText: '123' });
  const result = runTransaction((text) => text, {}, api);

  assert.deepEqual(result, { status: 'no-change' });
  assert.equal(api.calls.includes('paste'), false);
});

test('exceptions restore monitoring and the original clipboard', () => {
  const api = fakeAdapter({ selectionText: 'hello' });
  assert.throws(() => runTransaction(() => { throw new Error('boom'); }, {}, api), /boom/);

  assert.ok(api.calls.includes('enable'));
  assert.ok(api.calls.some((call) => Array.isArray(call) && call[0] === 'restore'));
});
