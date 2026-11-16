import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_LAYOUT_SIZES, fitDesktopLayoutSizes, normalizeLayoutSizes, resizeLayoutSizes } from '../src/layoutSizing.ts';

test('layout defaults are predictable and safe', () => {
  assert.deepEqual(DEFAULT_LAYOUT_SIZES, { leftWidth: 230, chatWidth: 430, stackedChatHeight: 680, composerHeight: 160 });
});

test('persisted sizes are normalized and clamped', () => {
  assert.deepEqual(normalizeLayoutSizes({ leftWidth: 9999, chatWidth: 5, stackedChatHeight: -2, composerHeight: 999 }), {
    leftWidth: 360, chatWidth: 340, stackedChatHeight: 420, composerHeight: 360,
  });
  assert.deepEqual(normalizeLayoutSizes({ leftWidth: NaN, chatWidth: 'wide' }), DEFAULT_LAYOUT_SIZES);
  assert.deepEqual(normalizeLayoutSizes(null), DEFAULT_LAYOUT_SIZES);
});

test('desktop left rail grows when dragged to the right', () => {
  const next = resizeLayoutSizes(DEFAULT_LAYOUT_SIZES, 'left-width', 48, 0, 1440);
  assert.equal(next.leftWidth, 278);
});

test('chat width grows when its left divider is dragged left', () => {
  const next = resizeLayoutSizes(DEFAULT_LAYOUT_SIZES, 'chat-width', -72, 0, 1440);
  assert.equal(next.chatWidth, 502);
});

test('stacked chat panel grows when its top divider is dragged upward', () => {
  const next = resizeLayoutSizes(DEFAULT_LAYOUT_SIZES, 'stacked-chat-height', 0, -90, 1440);
  assert.equal(next.stackedChatHeight, 770);
});

test('composer grows when its top grip is dragged upward and stays within bounds', () => {
  assert.equal(resizeLayoutSizes(DEFAULT_LAYOUT_SIZES, 'composer-height', 0, -64, 1440).composerHeight, 224);
  assert.equal(resizeLayoutSizes(DEFAULT_LAYOUT_SIZES, 'composer-height', 0, -900, 1440).composerHeight, 360);
});

test('saved desktop widths are fitted to a narrower window while preserving minimum panel widths', () => {
  const fitted = fitDesktopLayoutSizes({ ...DEFAULT_LAYOUT_SIZES, leftWidth: 360, chatWidth: 720 }, 1000);
  assert.deepEqual(fitted, { ...DEFAULT_LAYOUT_SIZES, leftWidth: 360, chatWidth: 720 }); // stacked layout
  const desktop = fitDesktopLayoutSizes({ ...DEFAULT_LAYOUT_SIZES, leftWidth: 360, chatWidth: 720 }, 1120);
  assert.ok(desktop.leftWidth + desktop.chatWidth <= 770);
  assert.ok(desktop.leftWidth >= 190);
  assert.ok(desktop.chatWidth >= 340);
});
