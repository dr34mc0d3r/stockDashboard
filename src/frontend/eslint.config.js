// ESLint flat config: the recommended JS rules, React, and the rules-of-hooks.
// Kept intentionally small — the goal is catching real mistakes (unused vars,
// broken hook deps), not enforcing a style guide; Prettier owns formatting.
import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import prettier from 'eslint-config-prettier'
import globals from 'globals'

export default [
  { ignores: ['dist/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // React 17+ JSX transform: no `import React` needed.
      'react/react-in-jsx-scope': 'off',
      'react/jsx-uses-react': 'off',
      // This project documents props with JSDoc, not prop-types.
      'react/prop-types': 'off',
      // The Lab pages are full of prose; escaping every apostrophe hurts more
      // than it helps.
      'react/no-unescaped-entities': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  // Node-side files (configs) use module/node globals.
  {
    files: ['*.config.js'],
    languageOptions: { globals: { ...globals.node } },
  },
  prettier,
]
