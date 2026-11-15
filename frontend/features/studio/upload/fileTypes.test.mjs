import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mimeForFile } from './fileTypes.ts';

test('Python source remains uploadable when a browser omits or generalizes its media type', () => {
  for (const mime of ['', 'text/plain', 'application/octet-stream', 'application/x-python', 'text/x-python-script']) {
    assert.equal(mimeForFile(mime, 'analysis.PY'), 'text/x-python');
  }
});

test('phone videos remain uploadable when a browser omits their media type', () => {
  for (const mime of ['', 'application/octet-stream']) {
    assert.equal(mimeForFile(mime, 'flat_01.MOV'), 'video/quicktime');
    assert.equal(mimeForFile(mime, 'clip.mp4'), 'video/mp4');
    assert.equal(mimeForFile(mime, 'clip.webm'), 'video/webm');
  }
  assert.equal(mimeForFile('video/quicktime', 'clip.mov'), 'video/quicktime');
  assert.equal(mimeForFile('text/plain', 'clip.mov'), 'text/plain');
});

test('normalization preserves explicitly identified media and does not guess unknown file types', () => {
  assert.equal(mimeForFile('Text/X-Python; charset=utf-8', 'analysis.py'), 'text/x-python');
  assert.equal(mimeForFile('image/png', 'misnamed.py'), 'image/png');
  assert.equal(mimeForFile('', 'unknown.bin'), '');
  assert.equal(mimeForFile('text/plain', 'notes.txt'), 'text/plain');
});
