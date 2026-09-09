import test from 'node:test';
import assert from 'node:assert/strict';
import { handleFeedback } from '../../src/lib/feedback-handler.ts';
import { validateFeedback } from '../../src/lib/feedback-schema.ts';
import { createScriptRuntime } from './script-runtime.mjs';

const submissionId = '12345678-1234-4234-8234-123456789012';
export const example = {
  name: ' TEST Person ', email: ' launch-test@example.com ', company: ' TEST Engineering ',
  role: 'Engineer', company_type: 'MEP Consultancy', phone: '',
  current_process: 'TEST manual drafting', time_sink: 'TEST routing',
  usefulness: 'Very useful', barriers: 'TEST accuracy', conversation: 'Yes', website: '', submissionId,
};
const config = { webhookUrl: 'https://script.google.com/macros/s/TEST_ENDPOINT/exec', webhookSecret: 'test-secret-not-a-credential-000000000000' };
function request(body = example, headers = {}) {
  return new Request('https://test.example/api/feedback', { method: 'POST', headers: { 'content-type': 'application/json', origin: 'https://test.example', ...headers }, body: typeof body === 'string' ? body : JSON.stringify(body) });
}
const neverSend = async () => { throw new Error('Unexpected network call'); };

test('trims fields, preserves every answer, ignores unrequested data, allows optional phone', () => {
  const result = validateFeedback({ ...example, password: 'must-not-store' });
  assert.equal(result.name, 'TEST Person');
  assert.equal(result.email, 'launch-test@example.com');
  assert.equal(result.company, 'TEST Engineering');
  assert.equal(result.phone, '');
  assert.equal(Object.keys(result).length, 11);
});
for (const key of ['name', 'email', 'company', 'role', 'company_type', 'current_process', 'time_sink', 'usefulness', 'barriers', 'conversation']) {
  test(`rejects whitespace-only required ${key}`, async () => {
    const response = await handleFeedback(request({ ...example, [key]: '  ' }), config, neverSend);
    assert.equal(response.status, 400);
  });
}
for (const [label, change] of [
  ['malformed email', { email: 'test@@example.com' }], ['honeypot', { website: 'spam' }],
  ['unknown choice', { usefulness: 'fake' }], ['invalid ID', { submissionId: 'bad' }],
  ['long name', { name: 'x'.repeat(121) }], ['wrong type', { company: {} }],
]) {
  test(`rejects ${label}`, async () => assert.equal((await handleFeedback(request({ ...example, ...change }), config, neverSend)).status, 400));
}
test('missing or unsafe configuration never returns success', async () => {
  for (const values of [{}, { ...config, webhookSecret: '' }, { ...config, webhookUrl: 'https://attacker.example/exec' }, { ...config, webhookUrl: config.webhookUrl.replace('/exec', '/dev') }]) {
    const response = await handleFeedback(request(), values, neverSend);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { ok: false, code: 'FORM_NOT_CONFIGURED' });
  }
});
test('enforces origin, content type, JSON and actual body size', async () => {
  assert.equal((await handleFeedback(request(example, { origin: 'https://attacker.example' }), config, neverSend)).status, 403);
  assert.equal((await handleFeedback(request(example, { 'content-type': 'text/plain' }), config, neverSend)).status, 415);
  assert.equal((await handleFeedback(request('{broken'), config, neverSend)).status, 400);
  assert.equal((await handleFeedback(request('x'.repeat(24001)), config, neverSend)).status, 413);
  assert.equal((await handleFeedback(request('null'), config, neverSend)).status, 400);
});
test('API to actual Apps Script logic: one correctly mapped row and timestamp; retry deduplicated', async () => {
  const runtime = createScriptRuntime();
  const send = async (url, init) => {
    assert.equal(url, config.webhookUrl);
    assert.equal(init.redirect, 'follow');
    const payload = JSON.parse(init.body);
    assert.equal(payload.secret, config.webhookSecret);
    assert.equal(payload.source_page, '/#feedback');
    return Response.json(runtime.post(payload));
  };
  for (let i = 0; i < 2; i++) {
    const response = await handleFeedback(request(), config, send);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ok: true, submissionId });
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
  assert.equal(runtime.rows.length, 2); // header + exactly one lead
  assert.ok(runtime.rows[1][0] instanceof Date);
  assert.deepEqual(runtime.rows[1].slice(1), ['TEST Person', 'launch-test@example.com', 'TEST Engineering', 'Engineer', 'MEP Consultancy', 'TEST manual drafting', 'TEST routing', 'Very useful', 'TEST accuracy', 'Yes', '', '/#feedback', submissionId]);
  assert.equal(runtime.released(), 2);
});
test('storage failures, non-JSON responses, false receipts and mismatched IDs never succeed', async () => {
  for (const send of [async () => { throw new Error('Timeout'); }, async () => new Response('Unavailable', { status: 500 }), async () => new Response('<html>Login</html>'), async () => Response.json({ ok: false }), async () => Response.json({ ok: true, submissionId: 'wrong' })]) {
    assert.equal((await handleFeedback(request(), config, send)).status, 502);
  }
});
test('Apps Script authenticates, validates, protects formulas and refuses changed headers', () => {
  const runtime = createScriptRuntime();
  const payload = { secret: runtime.secret, submissionId, fields: validateFeedback({ ...example, company: '=HYPERLINK("unsafe")', phone: '+919999999999' }) };
  assert.equal(runtime.post({ ...payload, secret: 'wrong' }).ok, false);
  assert.equal(runtime.post({ ...payload, fields: { ...payload.fields, email: 'bad' } }).ok, false);
  assert.equal(runtime.post(payload).ok, true);
  assert.equal(runtime.rows[1][3], "'=HYPERLINK(\"unsafe\")");
  assert.equal(runtime.rows[1][11], "'+919999999999");
  runtime.rows[0][1] = 'Wrong column';
  assert.equal(runtime.post({ ...payload, submissionId: '87654321-1234-4234-8234-123456789012' }).ok, false);
});
test('Apps Script cannot acknowledge failed writes or unavailable locks', () => {
  for (const options of [{ failWrite: true }, { lockAvailable: false }]) {
    const runtime = createScriptRuntime(options);
    assert.equal(runtime.post({ secret: runtime.secret, submissionId, fields: validateFeedback(example) }).ok, false);
    assert.equal(runtime.rows.length, 1);
  }
});
test('an uncertain response after append is safe to retry without adding another row', () => {
  const runtime = createScriptRuntime({ failFlush: true });
  const payload = { secret: runtime.secret, submissionId, fields: validateFeedback(example) };
  assert.equal(runtime.post(payload).ok, false);
  assert.equal(runtime.post(payload).ok, true);
  assert.equal(runtime.rows.length, 2);
});
