'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  smartTitleCase,
  cycleCase,
  transplantHebrewEnglish,
} = require('../transformations.js');

test('smart title case follows the configured small-word convention', () => {
  assert.equal(smartTitleCase('the lord of the rings'), 'The Lord of the Rings');
  assert.equal(smartTitleCase('war and peace'), 'War and Peace');
  assert.equal(smartTitleCase('a tale of two cities'), 'A Tale of Two Cities');
});

test('smart title case capitalizes after punctuation boundaries and hyphens', () => {
  assert.equal(
    smartTitleCase('notes: the rise-and-fall of empires — a history'),
    'Notes: The Rise-and-Fall of Empires — A History',
  );
});

test('smart title case preserves apostrophes while normalizing ordinary words', () => {
  assert.equal(smartTitleCase("THE ART OF DON'T PANIC"), "The Art of Don't Panic");
});

test('case toggle switches only between lower and upper', () => {
  const lower = 'the lord of the rings';
  const upper = 'THE LORD OF THE RINGS';

  assert.equal(cycleCase(lower), upper);
  assert.equal(cycleCase(upper), lower);
});

test('mixed or unknown case defaults to uppercase', () => {
  assert.equal(cycleCase('tHe lord OF the rings'), 'THE LORD OF THE RINGS');
});

test('single-letter uppercase toggles to lowercase', () => {
  assert.equal(cycleCase('A'), 'a');
  assert.equal(cycleCase('A B'), 'a b');
});

test('punctuation-only and empty strings are no-ops', () => {
  assert.equal(smartTitleCase('...'), '...');
  assert.equal(cycleCase('...'), '...');
  assert.equal(cycleCase(''), '');
});

test('English transplantation maps lowercase physical keys and preserves uppercase', () => {
  assert.equal(transplantHebrewEnglish('Hello'), 'Hקךךם');
  assert.equal(transplantHebrewEnglish('ABC abc'), 'ABC שנב');
});

test('Hebrew transplantation returns lowercase English', () => {
  assert.equal(transplantHebrewEnglish('שלום'), 'akuo');
});

test('transplantation preserves the existing physical punctuation map', () => {
  assert.equal(transplantHebrewEnglish('ab,./'), 'שנתץ.');
  assert.equal(transplantHebrewEnglish('שנתץ.'), 'ab,./');
});

test('alphabet ties and text without recognizable letters are no-ops', () => {
  assert.equal(transplantHebrewEnglish('aש'), 'aש');
  assert.equal(transplantHebrewEnglish('123 !?'), '123 !?');
});
