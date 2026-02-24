/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['data.assemblee-nationale.fr', 'upload.wikimedia.org'],
    formats: ['image/avif', 'image/webp'],
  },
  output: 'standalone',
}

module.exports = nextConfig
