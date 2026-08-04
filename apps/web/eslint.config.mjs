import nextVitals from 'eslint-config-next/core-web-vitals';

const config = [
  ...nextVitals,
  {
    ignores: [
      'tsconfig.tsbuildinfo',
      '.open-next/**',
      '.wrangler/**',
      'cloudflare-env.d.ts',
    ],
  },
];

export default config;
