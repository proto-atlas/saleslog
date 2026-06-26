import path from 'node:path'
import { fileURLToPath } from 'node:url'

// E2E のサーバ構成:
// - seeded: 8000(API) + 4173(preview)。API起動前に seed 投入
// - empty:  8010(API) + 4183(preview)。API起動前にテーブルのみ作成
const dirname = path.dirname(fileURLToPath(import.meta.url))

export const FRONTEND_DIR = path.resolve(dirname, '..')
export const BACKEND_DIR = path.resolve(dirname, '../../backend')
export const TMP_DIR = path.resolve(dirname, '.tmp')

function sqliteUrl(filePath: string): string {
  return `sqlite:///${filePath.replace(/\\/g, '/')}`
}

function envPort(name: string, defaultPort: number): number {
  const value = process.env[name]
  if (value === undefined || value.trim() === '') {
    return defaultPort
  }
  const port = Number(value)
  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    throw new Error(`${name} は 1 から 65535 の整数で指定してください`)
  }
  return port
}

export const SEEDED_DB_PATH = path.join(TMP_DIR, 'e2e-seeded.db')
export const EMPTY_DB_PATH = path.join(TMP_DIR, 'e2e-empty.db')
export const SEEDED_DB_URL = sqliteUrl(SEEDED_DB_PATH)
export const EMPTY_DB_URL = sqliteUrl(EMPTY_DB_PATH)

export const SEEDED_API_PORT = envPort('E2E_SEEDED_API_PORT', 8000)
export const EMPTY_API_PORT = envPort('E2E_EMPTY_API_PORT', 8010)
export const SEEDED_WEB_PORT = envPort('E2E_SEEDED_WEB_PORT', 4173)
export const EMPTY_WEB_PORT = envPort('E2E_EMPTY_WEB_PORT', 4183)

export const SEEDED_BASE_URL = `http://localhost:${SEEDED_WEB_PORT}`
export const EMPTY_BASE_URL = `http://localhost:${EMPTY_WEB_PORT}`

const isWindows = process.platform === 'win32'

// CI（Linux・システム python）では環境変数で上書きする
export const PYTHON_CMD =
  process.env.E2E_PYTHON ??
  path.join(BACKEND_DIR, '.venv', isWindows ? 'Scripts' : 'bin', 'python')
export const UVICORN_CMD =
  process.env.E2E_UVICORN ??
  path.join(BACKEND_DIR, '.venv', isWindows ? 'Scripts' : 'bin', 'uvicorn')
