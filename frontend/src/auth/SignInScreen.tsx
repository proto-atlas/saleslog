import { SignIn } from '@clerk/react'

export function SignInScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-6">
        <h1 className="text-xl font-bold text-gray-900">Saleslog</h1>
        <SignIn />
      </div>
    </main>
  )
}
