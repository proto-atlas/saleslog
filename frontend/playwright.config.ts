import { defineConfig } from 'playwright/test'

import {
  BACKEND_DIR,
  EMPTY_API_PORT,
  EMPTY_BASE_URL,
  EMPTY_DB_URL,
  EMPTY_WEB_PORT,
  FRONTEND_DIR,
  PYTHON_CMD,
  SEEDED_API_PORT,
  SEEDED_BASE_URL,
  SEEDED_DB_URL,
  SEEDED_WEB_PORT,
  UVICORN_CMD,
} from './e2e/servers'

export default defineConfig({
  testDir: './e2e',
  // 書き込み系シナリオがあるため直列実行
  workers: 1,
  // 4サーバ同時起動直後の初回描画は遅くなることがあるため、既定の5秒では足りない
  expect: { timeout: 10_000 },
  projects: [
    {
      name: 'seeded',
      testIgnore: /empty/,
      use: { baseURL: SEEDED_BASE_URL },
    },
    {
      name: 'empty-db',
      testMatch: /empty/,
      use: { baseURL: EMPTY_BASE_URL },
    },
  ],
  webServer: [
    {
      // Playwright は webServer を globalSetup より先に起動するため、API起動前にDBを作成する。
      command: `"${PYTHON_CMD}" -m app.seed --reset-schema && "${UVICORN_CMD}" app.main:app --port ${SEEDED_API_PORT}`,
      cwd: BACKEND_DIR,
      env: { AUTH_MODE: 'fixed', DATABASE_URL: SEEDED_DB_URL },
      url: `http://localhost:${SEEDED_API_PORT}/openapi.json`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `"${PYTHON_CMD}" -m app.seed --reset-schema --empty && "${UVICORN_CMD}" app.main:app --port ${EMPTY_API_PORT}`,
      cwd: BACKEND_DIR,
      env: { AUTH_MODE: 'fixed', DATABASE_URL: EMPTY_DB_URL },
      url: `http://localhost:${EMPTY_API_PORT}/openapi.json`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // build はテスト実行前に必ず行う（package.json の e2e スクリプト）。
      // preview はディスクの dist を配信するだけなので、再利用サーバでも新しい build が反映される
      command: `npm run preview -- --port ${SEEDED_WEB_PORT} --strictPort`,
      cwd: FRONTEND_DIR,
      env: { FIELDOPS_API_PORT: String(SEEDED_API_PORT) },
      url: SEEDED_BASE_URL,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run preview -- --port ${EMPTY_WEB_PORT} --strictPort`,
      cwd: FRONTEND_DIR,
      env: { FIELDOPS_API_PORT: String(EMPTY_API_PORT) },
      url: EMPTY_BASE_URL,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
