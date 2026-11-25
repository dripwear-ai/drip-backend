/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@drip/shared-types'],
  distDir: process.env.NEXT_PORTAL_DIST_DIR || '.next',
};

export default nextConfig;
