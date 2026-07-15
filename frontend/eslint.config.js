import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // TanStack Router file-based routes MUST export the `Route` value (and
    // the root route its context type) alongside their components — that is
    // the framework contract, so the Fast Refresh purity rule can't apply
    // here. The router plugin handles HMR for route files itself.
    files: ['src/routes/**/*.{ts,tsx}', 'src/routeTree.gen.ts'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
