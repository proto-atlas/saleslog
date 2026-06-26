import { execFileSync } from 'node:child_process'

import { BACKEND_DIR, PYTHON_CMD, SEEDED_DB_URL } from './servers'

// 書き込み系シナリオの前に seed を入れ直して前後依存を断つ
export function reseed(): void {
  execFileSync(PYTHON_CMD, ['-m', 'app.seed'], {
    cwd: BACKEND_DIR,
    env: { ...process.env, DATABASE_URL: SEEDED_DB_URL },
    stdio: 'inherit',
  })
}
