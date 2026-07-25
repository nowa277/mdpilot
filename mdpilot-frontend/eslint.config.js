import boundaries from 'eslint-plugin-boundaries';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: ['dist', 'node_modules', 'coverage', '.vite', 'eslint.config.js', 'public'],
  },
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        project: ['./tsconfig.json', './tsconfig.node.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'simple-import-sort': simpleImportSort,
      boundaries,
    },
    settings: {
      react: { version: '18.3' },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app/**' },
        { type: 'feature', pattern: 'src/features/(*)/**', mode: 'folder', capture: ['feature'] },
        { type: 'shared', pattern: 'src/shared/**' },
        { type: 'mocks', pattern: 'src/mocks/**' },
        { type: 'styles', pattern: 'src/styles/**' },
        { type: 'entry', pattern: 'src/main.tsx' },
      { type: 'tests', pattern: 'tests/**' },
      ],
    },
    rules: {
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'no-console': 'warn',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: [
      { from: 'entry', allow: ['app', 'shared', 'mocks', 'styles'] },
            { from: 'app', allow: ['app', 'shared', 'feature'] },
            {
            from: 'feature',
            allow: [
              'shared',
         // features 之间只能引用对方的 index.ts（通过 element-pattern + capture）
              ['feature', { feature: '!${from.feature}' }],
            ],
          },
        { from: 'shared', allow: ['shared'] },
            { from: 'mocks', allow: ['mocks', 'shared'] },
          { from: 'tests', allow: ['app', 'feature', 'shared', 'mocks'] },
        ],
        },
      ],
    },
  },
);
