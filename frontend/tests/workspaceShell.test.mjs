import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const app = await readFile(resolve(here, '../src/App.tsx'), 'utf8');
const css = await readFile(resolve(here, '../src/styles.css'), 'utf8');

test('all JARVIS workspaces share one system navigation rail', () => {
  for (const label of ['Assistant', 'Intelligence core', 'Memory', 'Operations', 'Self development', 'System diagnostics']) {
    assert.ok(app.includes(`>${label}</span>`), `missing workspace navigation item: ${label}`);
  }
  assert.match(app, /className="left-rail panel"[\s\S]*className="workspace-nav"/);
  assert.match(app, /className="main-workspace panel"/);
  assert.doesNotMatch(app, /className="right-rail panel"/);
});

test('chat is the default primary workspace and the hologram remains selectable', () => {
  assert.match(app, /useState<[^>]*'chat'[^>]*>\('chat'\)/);
  assert.match(app, /panel === 'hologram'/);
  assert.match(app, /panel === 'chat' && <div className="chat-panel"/);
});

test('desktop gives the main workspace all space after the compact rail', () => {
  assert.match(css, /grid-template-columns:\s*minmax\(200px,[^;]+\) minmax\(0, 1fr\)/);
  assert.match(css, /\.main-workspace\s*\{[^}]*width:\s*100%/);
});

test('mobile collapses navigation horizontally and keeps the workspace full-width', () => {
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.workspace-nav\s*\{[^}]*flex-direction:\s*row/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.main-workspace\s*\{[^}]*width:\s*100%/);
});
