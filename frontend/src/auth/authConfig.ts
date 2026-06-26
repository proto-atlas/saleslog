export const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined

// 未設定時はフロントの認証UIとBearer付与を無効化する。
// ローカル固定ユーザーで動かす場合はバックエンドに AUTH_MODE=fixed を設定する。
export const authEnabled =
  clerkPublishableKey !== undefined && clerkPublishableKey !== ''
