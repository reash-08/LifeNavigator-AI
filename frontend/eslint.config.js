export default [
  { ignores: ['dist/**'] },
  {
    files: ['**/*.js'],
    languageOptions: { ecmaVersion: 2022, sourceType: 'module', globals: { document: 'readonly', window: 'readonly', localStorage: 'readonly', fetch: 'readonly', URLSearchParams: 'readonly', FormData: 'readonly', Intl: 'readonly', console: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly', HTMLElement: 'readonly', process: 'readonly' } },
    rules: { 'no-unused-vars': ['error', { argsIgnorePattern: '^_' }], 'no-constant-condition': 'error' },
  },
];
