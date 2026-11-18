import test from 'node:test'
import assert from 'node:assert/strict'
import { describeDetail } from '../.unit-build/requestErrors.js'

const issue = (loc, msg) => ({ loc, msg })

test('an unticked consent box reads as an Indonesian instruction, not a pydantic message', () => {
  assert.equal(describeDetail([issue(['body', 'consent'], 'Input should be True')]), 'Persetujuan wajib dicentang.')
})

test('missing, too short and too long values name the field in Indonesian', () => {
  assert.equal(describeDetail([issue(['body', 'full_name'], 'Field required')]), 'Nama lengkap wajib diisi.')
  assert.equal(describeDetail([issue(['body', 'password'], 'String should have at least 8 characters')]), 'Kata sandi minimal 8 karakter.')
  assert.equal(describeDetail([issue(['body', 'full_name'], 'String should have at most 160 characters')]), 'Nama lengkap maksimal 160 karakter.')
})

test('an email the server rejects is explained without the library text', () => {
  const text = describeDetail([issue(['body', 'email'],
    'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.')])
  assert.equal(text, 'Email tidak valid. Gunakan alamat email yang aktif.')
})

test('messages the server already wrote in Indonesian pass through, with or without a field', () => {
  assert.equal(describeDetail([issue(['body'], 'Nomor telepon wajib diisi.')]), 'Nomor telepon wajib diisi.')
  assert.equal(describeDetail([issue(['body', 'phone'], 'Format nomor telepon tidak valid.')]), 'Nomor telepon: Format nomor telepon tidak valid.')
})

test('several issues are joined and an unknown field keeps its own name', () => {
  assert.equal(describeDetail([issue(['body', 'consent'], 'Input should be True'), issue(['body', 'nickname'], 'Field required')]),
    'Persetujuan wajib dicentang. nickname wajib diisi.')
})
