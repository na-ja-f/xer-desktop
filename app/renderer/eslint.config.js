import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      // tseslint.parser parses plain JS/JSX identically to the previous
      // default (espree), so this is safe for existing files too — it's
      // required so this block can parse .ts/.tsx syntax at all.
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  {
    files: ['src/**/*.{js,jsx,ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', {
        paths: ['electron', 'fs', 'path', 'os', 'child_process', 'net', 'http', 'https', 'crypto', 'util'].map(name => ({
          name,
          message: `Renderer must not import Node/Electron module "${name}". Use window.xerAgent (the bridge) instead.`,
        })),
        patterns: [{ group: ['node:*', 'electron/*'], message: 'Renderer must not import Node/Electron modules.' }],
      }],
      'no-restricted-syntax': ['error',
        { selector: "MemberExpression[object.name='window'][property.name='require']", message: 'Renderer must not call window.require(). Use window.xerAgent instead.' },
        { selector: "MemberExpression[object.name='window'][property.name='process']", message: 'Renderer must not read window.process. Use window.xerAgent.getUserContext() instead.' },
        { selector: "CallExpression[callee.name='require']", message: 'Renderer must not call require(). Use ES imports or window.xerAgent.' },
      ],
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [tseslint.configs.strict],
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
])
