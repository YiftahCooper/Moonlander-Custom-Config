'use strict';

(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.MoonlanderTransforms = api;
}(this, function () {
  var SMALL_WORDS = {
    a: true, an: true, and: true, as: true, at: true, but: true,
    by: true, for: true, in: true, nor: true, of: true, on: true,
    or: true, per: true, so: true, the: true, to: true, up: true,
    via: true, vs: true, yet: true,
  };

  var ENGLISH_TO_HEBREW = {
    q: '/', w: "'", e: '\u05e7', r: '\u05e8', t: '\u05d0', y: '\u05d8',
    u: '\u05d5', i: '\u05df', o: '\u05dd', p: '\u05e4',
    '[': '}', ']': '{', '\\': '|',
    a: '\u05e9', s: '\u05d3', d: '\u05d2', f: '\u05db', g: '\u05e2', h: '\u05d9',
    j: '\u05d7', k: '\u05dc', l: '\u05da', ';': '\u05e3', "'": ',',
    z: '\u05d6', x: '\u05e1', c: '\u05d1', v: '\u05d4', b: '\u05e0',
    n: '\u05de', m: '\u05e6', ',': '\u05ea', '.': '\u05e5', '/': '.',
  };

  var HEBREW_TO_ENGLISH = {};
  Object.keys(ENGLISH_TO_HEBREW).forEach(function (english) {
    var hebrew = ENGLISH_TO_HEBREW[english];
    if (!Object.prototype.hasOwnProperty.call(HEBREW_TO_ENGLISH, hebrew)) {
      HEBREW_TO_ENGLISH[hebrew] = english;
    }
  });

  function capitalize(word) {
    var normalized = word.toLowerCase();
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function isTitleBoundary(separator) {
    return /:/.test(separator)
      || /[\u2013\u2014]/.test(separator)
      || (/-/.test(separator) && /\s/.test(separator));
  }

  function smartTitleCase(text) {
    var source = String(text);
    var wordPattern = /[A-Za-z]+(?:['\u2019][A-Za-z]+)*/g;
    var matches = source.match(wordPattern);
    if (!matches || matches.length === 0) {
      return source;
    }

    var lexicalIndex = 0;
    var previousEnd = 0;
    return source.replace(wordPattern, function (word, offset) {
      var separator = source.slice(previousEnd, offset);
      var lower = word.toLowerCase();
      var isFirst = lexicalIndex === 0;
      var isLast = lexicalIndex === matches.length - 1;
      var forceCapital = isFirst || isLast || isTitleBoundary(separator);
      var result = forceCapital || !SMALL_WORDS[lower] ? capitalize(lower) : lower;
      lexicalIndex += 1;
      previousEnd = offset + word.length;
      return result;
    });
  }

  function cycleCase(text) {
    var source = String(text);
    var lower = source.toLowerCase();
    var upper = source.toUpperCase();
    if (lower === upper) {
      return source;
    }
    if (source === upper) {
      return lower;
    }
    return upper;
  }

  function countMatches(text, pattern) {
    var matches = text.match(pattern);
    return matches ? matches.length : 0;
  }

  function mapCharacters(text, mapping) {
    return Array.from(text).map(function (character) {
      return Object.prototype.hasOwnProperty.call(mapping, character)
        ? mapping[character]
        : character;
    }).join('');
  }

  function transplantHebrewEnglish(text) {
    var source = String(text);
    var englishCount = countMatches(source, /[a-z]/g);
    var hebrewCount = countMatches(source, /[\u05d0-\u05ea]/g);
    if (englishCount === hebrewCount) {
      return source;
    }
    if (englishCount > hebrewCount) {
      return mapCharacters(source, ENGLISH_TO_HEBREW);
    }
    return mapCharacters(source, HEBREW_TO_ENGLISH);
  }

  return {
    SMALL_WORDS: SMALL_WORDS,
    smartTitleCase: smartTitleCase,
    cycleCase: cycleCase,
    transplantHebrewEnglish: transplantHebrewEnglish,
  };
}));
