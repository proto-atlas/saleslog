import { spawnSync } from 'node:child_process'

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const result = spawnSync(npmCommand, ['run', 'build'], {
  env: { ...process.env, VITE_DEMO_MODE: 'static' },
  shell: true,
  stdio: 'inherit',
})

if (result.error !== undefined) {
  console.error(result.error.message)
}

process.exit(result.status ?? 1)
