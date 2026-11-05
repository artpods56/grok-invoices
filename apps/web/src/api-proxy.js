// Only public read endpoints are exposed. No cookies, keys, or write requests are forwarded.
const allowed = /^(client|accounts|invoices(?:\/[1-9]\d*)?|cases(?:\/[1-9]\d*)?|questions|events)$/;

export async function proxyPlatformRead(request, path, { baseUrl = process.env.API_BASE_URL || 'http://127.0.0.1:8000', fetcher = fetch } = {}) {
  if (!Array.isArray(path) || !allowed.test(path.join('/'))) return Response.json({ error: 'Unknown platform endpoint.' }, { status: 404 });
  const target = new URL(`/api/${path.join('/')}`, baseUrl);
  try {
    const response = await fetcher(target, {
      method: 'GET', headers: { Accept: 'application/json' }, cache: 'no-store',
      redirect: 'error', signal: AbortSignal.any([request.signal, AbortSignal.timeout(10000)]),
    });
    if (!response.ok) return Response.json({ error: 'Platform request failed.' }, { status: response.status });
    const data = await response.json();
    return Response.json(data, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'Platform is unavailable. Please retry.' }, { status: 502 });
  }
}
