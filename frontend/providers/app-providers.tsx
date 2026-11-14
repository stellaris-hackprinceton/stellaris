'use client'

import { createContext, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import type { Capabilities, Session } from '@/contracts/api'
import { isAuthError, setCsrfToken } from '@/lib/api'
import { keys, useCapabilities, useSession } from '@/lib/queries'
import styles from '@/features/execution/sol.module.css'

const SessionContext = createContext<{ session: Session, capabilities: Capabilities } | null>(null)
export function useAppSession() {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useAppSession requires SessionGate.')
  return value
}
function SessionGate({ children }: { children: ReactNode }) {
  const client = useQueryClient(), session = useSession(), capabilities = useCapabilities()
  const [expired, setExpired] = useState(false)
  useEffect(() => {
    const expire = () => { setCsrfToken(null); setExpired(true); void client.cancelQueries({ predicate: q => q.queryKey[0] !== 'session' }); client.removeQueries({ predicate: q => q.queryKey[0] !== 'session' }); client.setQueryData(keys.session, null) }
    window.addEventListener('stellaris:auth-expired', expire)
    return () => { window.removeEventListener('stellaris:auth-expired', expire); setCsrfToken(null) }
  }, [client])
  useLayoutEffect(() => {
    if (!session.data) return
    setCsrfToken(session.data.csrf_token)
  }, [session.data, client])
  async function reconnect() {
    const resolved = await session.refetch()
    if (!resolved.error && resolved.data) {
      setCsrfToken(resolved.data.csrf_token)
      setExpired(false)
      await client.invalidateQueries({ queryKey: keys.capabilities })
    }
  }
  if (expired || isAuthError(session.error)) {
    const login = process.env.NEXT_PUBLIC_LOGIN_URL
    const allowedLogin = login && (login.startsWith('/') && !login.startsWith('//') || login.startsWith('https://')) ? login : null
    return <main className={styles.screen}><h1>Sign in to Stellaris</h1><p>Your research session is unavailable or has expired.</p>{allowedLogin ? <a href={allowedLogin}>Sign in</a> : <p>A login entry point has not been configured. Ask the backend owner to configure authentication.</p>}<button onClick={() => void reconnect()}>Check session again</button></main>
  }
  if (session.error || capabilities.error) return <main className={styles.screen}><h1>Stellaris is unavailable</h1><p>The research backend could not be reached or returned an error. No project data has been replaced.</p><p role="alert">{(session.error ?? capabilities.error)?.message}</p><button onClick={() => void reconnect()}>Retry connection</button><a href="/docs/README.md">Read integration documentation</a></main>
  if (!session.data || !capabilities.data) return <main className={styles.screen} aria-busy="true"><h1>Opening Stellaris</h1><p>Resolving session and available research tools…</p></main>
  return <SessionContext.Provider key={session.data.user.id} value={{ session: session.data, capabilities: capabilities.data }}>{children}</SessionContext.Provider>
}
export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 15000, refetchOnWindowFocus: false }, mutations: { retry: false } } }))
  return <QueryClientProvider client={client}><SessionGate>{children}</SessionGate></QueryClientProvider>
}
