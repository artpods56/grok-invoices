import test from 'node:test';
import assert from 'node:assert/strict';
import { proxyPlatformRead } from '../src/api-proxy.js';

test('invalid backend configuration fails safely before a network call', async () => {
  for (const baseUrl of ['invalid-url', 'file:///private', 'https://user:password@example.com']) {
    const response = await proxyPlatformRead(new Request('http://web/'), ['client'], {
      baseUrl, fetcher: () => assert.fail('Invalid configuration must not be fetched'),
    });
    assert.equal(response.status, 502);
    assert.equal((await response.text()).includes('password'), false);
  }
});

test('proxy only forwards public GET data without user credentials', async () => {
  const request = new Request('http://web/api/invoices/3?secret=example', { headers: { Authorization: 'Bearer example', Cookie: 'session=example' } });
  const result = await proxyPlatformRead(request, ['invoices', '3'], {
    baseUrl: 'http://api:8000', fetcher: async (url, options) => {
      assert.equal(url.href, 'http://api:8000/api/invoices/3');
      assert.equal(options.method, 'GET');
      assert.deepEqual(options.headers, { Accept: 'application/json' });
      assert.equal(options.cache, 'no-store');
      return Response.json({ id: 3 });
    },
  });
  assert.deepEqual(await result.json(), { id: 3 });
  assert.equal(result.headers.get('Cache-Control'), 'no-store');
});

test('proxy rejects traversal, write and arbitrary endpoints before fetch', async () => {
  for (const path of [['..', 'health'], ['demo', 'reset'], ['invoices', '0'], ['https:', 'example.com'], ['invoices', '1', 'postings']]) {
    const result = await proxyPlatformRead(new Request('http://web/'), path, { fetcher: () => assert.fail('Unexpected request') });
    assert.equal(result.status, 404);
  }
});

test('proxy reports upstream failure without disclosing response contents', async () => {
  const request = new Request('http://web/');
  const failed = await proxyPlatformRead(request, ['client'], { fetcher: async () => new Response('internal secret', { status: 503 }) });
  assert.equal(failed.status, 503);
  assert.equal((await failed.text()).includes('internal secret'), false);
  const offline = await proxyPlatformRead(request, ['client'], { fetcher: async () => { throw Error('private address'); } });
  assert.equal(offline.status, 502);
});
