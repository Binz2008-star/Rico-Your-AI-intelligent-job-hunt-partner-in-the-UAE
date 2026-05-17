import nextVitals from 'eslint-config-next/core-web-vitals';

export default [
  ...nextVitals,
  {
    ignores: [
      'tsconfig.tsbuildinfo',
    ],
  },
];
