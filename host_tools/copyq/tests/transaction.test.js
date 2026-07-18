'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { runTransaction } = require('../transaction.js');

function fakeAdapter(options = {}) {
  const calls = [];
  const scheduled = [];
  const state = options.state || { generation: 0, active: null };
  const environment = options.environment || {
    item: { 'text/plain': 'old text', 'image/png': '<binary>' },
    monitoring: options.monitoring === undefined ? true : options.monitoring,
  };

  const adapter = {
    calls,
    scheduled,
    state,
    environment,
    snapshotClipboard() {
      calls.push('snapshot');
      return { ...environment.item };
    },
    isMonitoring() { calls.push('monitoring'); return environment.monitoring; },
    disableMonitoring() { calls.push('disable'); environment.monitoring = false; },
    enableMonitoring() { calls.push('enable'); environment.monitoring = true; },
    captureSelection() {
      calls.push('capture');
      if (options.captureError) {
        environment.item = {};
        throw new Error('capture failed');
      }
      const text = options.selectionText === undefined ? 'selected text' : options.selectionText;
      environment.item = { 'text/plain': text };
    },
    readText() { calls.push('read'); return environment.item['text/plain'] || ''; },
    writeText(text) {
      calls.push(['write', text]);
      environment.item = { 'text/plain': text };
    },
    paste() {
      calls.push('paste');
      if (options.pasteError) {
        throw new Error('paste failed');
      }
    },
    schedule(milliseconds, callback) {
      calls.push(['schedule', milliseconds]);
      scheduled.push({ milliseconds, callback });
    },
    reselect(text) {
      calls.push(['reselect', text]);
      return options.reselectExitCode || 0;
    },
    restoreClipboard(item) {
      calls.push(['restore', item]);
      environment.item = { ...item };
    },
    log(message) { calls.push(['log', String(message)]); },
  };
  return adapter;
}

function runScheduled(adapter, milliseconds) {
  const task = adapter.scheduled.find((entry) => entry.milliseconds === milliseconds);
  assert.ok(task, `No callback scheduled for ${milliseconds} ms`);
  task.callback();
}

test('transaction pastes immediately and restores every clipboard format asynchronously', () => {
  const api = fakeAdapter({ selectionText: 'hello' });
  const original = { ...api.environment.item };
  const result = runTransaction((text) => text.toUpperCase(), {}, api);

  assert.deepEqual(result, { status: 'transformed', text: 'HELLO' });
  assert.equal(api.environment.item['text/plain'], 'HELLO');
  assert.equal(api.calls.includes('paste'), true);
  assert.equal(api.calls.some((call) => Array.isArray(call) && call[0] === 'restore'), false);
  assert.deepEqual(api.scheduled.map((entry) => entry.milliseconds), [250]);

  runScheduled(api, 250);
  assert.deepEqual(api.environment.item, original);
});

test('case transaction schedules reselection after paste and restoration independently', () => {
  const api = fakeAdapter({ selectionText: 'lower' });
  runTransaction((text) => text.toUpperCase(), { reselect: true }, api);

  assert.deepEqual(api.scheduled.map((entry) => entry.milliseconds), [35, 250]);
  assert.equal(api.calls.some((call) => Array.isArray(call) && call[0] === 'reselect'), false);

  runScheduled(api, 35);
  assert.ok(api.calls.some((call) => Array.isArray(call)
    && call[0] === 'reselect' && call[1] === 'LOWER'));
  assert.equal(api.environment.item['text/plain'], 'LOWER');

  runScheduled(api, 250);
  assert.equal(api.environment.item['text/plain'], 'old text');
});

test('rapid repeated transactions invalidate old callbacks and restore the first snapshot', () => {
  const state = { generation: 0, active: null };
  const environment = {
    item: { 'text/plain': 'original clipboard', 'image/png': '<binary>' },
    monitoring: true,
  };
  const first = fakeAdapter({ state, environment, selectionText: 'lower' });
  runTransaction((text) => text.toUpperCase(), { reselect: true }, first);
  runScheduled(first, 35);

  const second = fakeAdapter({ state, environment, selectionText: 'LOWER' });
  runTransaction((text) => text.toLowerCase(), { reselect: true }, second);
  assert.equal(second.calls.includes('snapshot'), false);

  runScheduled(first, 250);
  assert.equal(environment.item['text/plain'], 'lower');

  runScheduled(second, 35);
  runScheduled(second, 250);
  assert.deepEqual(environment.item, {
    'text/plain': 'original clipboard',
    'image/png': '<binary>',
  });
});

test('a newer clipboard change is never overwritten during delayed restoration', () => {
  const api = fakeAdapter({ selectionText: 'hello' });
  runTransaction((text) => text.toUpperCase(), {}, api);
  api.environment.item = { 'text/plain': 'new user copy' };

  runScheduled(api, 250);
  assert.equal(api.environment.item['text/plain'], 'new user copy');
  assert.equal(api.calls.some((call) => Array.isArray(call) && call[0] === 'restore'), false);
});

test('originally disabled monitoring remains disabled', () => {
  const api = fakeAdapter({ selectionText: 'hello', monitoring: false });
  runTransaction((text) => text.toUpperCase(), {}, api);

  assert.equal(api.calls.includes('enable'), false);
});

test('empty selection aborts without pasting and restores the clipboard', () => {
  const api = fakeAdapter({ selectionText: '' });
  const original = { ...api.environment.item };
  const result = runTransaction((text) => text.toUpperCase(), {}, api);

  assert.deepEqual(result, { status: 'no-selection' });
  assert.equal(api.calls.includes('paste'), false);
  assert.deepEqual(api.environment.item, original);
  assert.deepEqual(api.scheduled, []);
});

test('a no-op transform restores clipboard without pasting', () => {
  const api = fakeAdapter({ selectionText: '123' });
  const original = { ...api.environment.item };
  const result = runTransaction((text) => text, {}, api);

  assert.deepEqual(result, { status: 'no-change' });
  assert.equal(api.calls.includes('paste'), false);
  assert.deepEqual(api.environment.item, original);
});

for (const failure of ['captureError', 'pasteError']) {
  test(`${failure} is logged and contained without an error dialog`, () => {
    const api = fakeAdapter({ selectionText: 'hello', [failure]: true });
    const original = { ...api.environment.item };
    const result = runTransaction((text) => text.toUpperCase(), {}, api);

    assert.deepEqual(result, { status: 'error' });
    assert.deepEqual(api.environment.item, original);
    assert.equal(api.environment.monitoring, true);
    assert.ok(api.calls.some((call) => Array.isArray(call)
      && call[0] === 'log' && call[1].includes('failed')));
  });
}

test('reselection failure is logged and does not prevent restoration', () => {
  const api = fakeAdapter({ selectionText: 'lower', reselectExitCode: 3 });
  runTransaction((text) => text.toUpperCase(), { reselect: true }, api);

  runScheduled(api, 35);
  assert.ok(api.calls.some((call) => Array.isArray(call)
    && call[0] === 'log' && call[1].includes('exit code 3')));

  runScheduled(api, 250);
  assert.equal(api.environment.item['text/plain'], 'old text');
});
