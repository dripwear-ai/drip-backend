import js from '@eslint/js';

export default [
  { ignores: ['**/node_modules/**', '**/dist/**', '**/.next/**', '**/.expo/**', '.verification/**', '.cache/**', '.pnpm-store/**'] },
  { ...js.configs.recommended, files: ['scripts/**/*.mjs', 'eslint.config.mjs'],
    languageOptions: { globals: { console: 'readonly', process: 'readonly' } } },
];
