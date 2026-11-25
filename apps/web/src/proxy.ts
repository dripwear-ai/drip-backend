import { NextResponse, type NextRequest } from 'next/server';

const surface = process.env.DRIP_PORTAL_SURFACE;

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (path === '/') {
    if (surface === 'admin' || surface === 'seller') {
      return NextResponse.redirect(new URL(`/${surface}`, request.url));
    }
    return new NextResponse('Portal surface is not configured.', { status: 404, headers: { 'Cache-Control': 'no-store' } });
  }

  if (surface !== 'admin' && surface !== 'seller') {
    return new NextResponse('Not found.', { status: 404, headers: { 'Cache-Control': 'no-store' } });
  }

  const allowedPrefix = `/${surface}`;
  if (path !== allowedPrefix && !path.startsWith(`${allowedPrefix}/`)) {
    return new NextResponse('Not found.', { status: 404, headers: { 'Cache-Control': 'no-store' } });
  }
  return NextResponse.next();
}

export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt).*)'] };
