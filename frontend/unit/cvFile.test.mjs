import test from 'node:test'
import assert from 'node:assert/strict'
import { cvAction, cvCaption, formatSize } from '../.unit-build/cvFile.js'

test('file sizes read as B, KB or MB', () => {
  assert.equal(formatSize(512), '512 B')
  assert.equal(formatSize(125224), '122 KB')
  assert.equal(formatSize(2.5 * 1024 * 1024), '2.5 MB')
})

test('a PDF opens in a new tab, a Word file is downloaded', () => {
  assert.equal(cvAction('application/pdf'), 'open')
  assert.equal(cvAction('application/vnd.openxmlformats-officedocument.wordprocessingml.document'), 'download')
  assert.equal(cvAction('application/msword'), 'download')
})

test('the caption shows the file name and its size', () => {
  assert.equal(cvCaption({ filename: 'cv-sari.pdf', size_bytes: 125224, content_type: 'application/pdf' }), 'cv-sari.pdf · 122 KB')
})
