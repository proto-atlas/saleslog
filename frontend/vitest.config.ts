import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, mergeConfig } from 'vitest/config'
import { playwright } from '@vitest/browser-playwright'
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin'

import viteConfig from './vite.config'

const dirname = path.dirname(fileURLToPath(import.meta.url))

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      coverage: {
        provider: 'v8',
        reporter: ['text', 'html'],
        // 分母はロジックを持つモジュールに固定する
        include: [
          'src/lib/**',
          'src/hooks/**',
          'src/api/enums.ts',
          'src/pages/customers/customerFormSchema.ts',
          'src/pages/visits/visitFormSchema.ts',
        ],
        exclude: ['src/**/*.test.{ts,tsx}', 'src/api/generated/**'],
        thresholds: {
          statements: 80,
          branches: 80,
        },
      },
      projects: [
        {
          extends: true,
          test: {
            name: 'unit',
            include: ['src/**/*.test.{ts,tsx}'],
            // RTL（renderHook）が DOM を要するため、storybook 側と同じ browser mode に統一
            browser: {
              enabled: true,
              provider: playwright({}),
              headless: true,
              instances: [{ browser: 'chromium' }],
            },
          },
        },
        {
          extends: true,
          plugins: [
            storybookTest({
              configDir: path.join(dirname, '.storybook'),
              storybookScript: 'npm run storybook -- --no-open',
            }),
          ],
          test: {
            name: 'storybook',
            browser: {
              enabled: true,
              provider: playwright({}),
              headless: true,
              instances: [{ browser: 'chromium' }],
            },
          },
        },
      ],
    },
  }),
)
