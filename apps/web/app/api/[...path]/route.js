import { proxyPlatformRead } from '../../../src/api-proxy.js';

export const dynamic = 'force-dynamic';

export async function GET(request, { params }) {
  const { path } = await params;
  return proxyPlatformRead(request, path);
}
