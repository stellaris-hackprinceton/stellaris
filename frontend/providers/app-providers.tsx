'use client'

import { createContext, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import type { Capabilities, Session } from '@/contracts/api'
import { isAuthError, setCsrfToken } from '@/lib/api'
import { keys, useCapabilities, useSession } from '@/lib/queries'
import styles from '@/features/execution/sol.module.css'
import { ConnectionNotice } from './connection-notice'
import { SignInRequired } from '@/features/projects'

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
    setCsrfToken(session.data.csrf_token, session.data.auth_mode)
  }, [session.data, client])
  async function reconnect() {
    const resolved = await session.refetch()
    if (!resolved.error && resolved.data) {
      setCsrfToken(resolved.data.csrf_token, resolved.data.auth_mode)
      setExpired(false)
      await client.invalidateQueries({ queryKey: keys.capabilities })
    }
  }
  if (expired || isAuthError(session.error)) {
    const login = process.env.NEXT_PUBLIC_LOGIN_URL
    const allowedLogin = login && (login.startsWith('/') && !login.startsWith('//') || login.startsWith('https://')) ? login : null
    return <><SignInRequired login_url={allowedLogin} expired={expired} /><div className={styles.screen}><button disabled={session.isFetching} onClick={() => void reconnect()}>Check session again</button></div></>
  }
  if (session.error || capabilities.error) return <ConnectionNotice error={session.error ?? capabilities.error} endpoint={session.error ? '/api/v1/session' : '/api/v1/capabilities'} pending={session.isFetching || capabilities.isFetching} retry={() => void reconnect()} />
  if (!session.data || !capabilities.data) return <main className={styles.screen} aria-busy="true"><h1>Opening Stellaris</h1><p>Resolving session and available research tools…</p></main>
  return <SessionContext.Provider key={session.data.user.id} value={{ session: session.data, capabilities: capabilities.data }}>{children}</SessionContext.Provider>
}
export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 15000, refetchOnWindowFocus: false }, mutations: { retry: false } } }))
  return <QueryClientProvider client={client}><SessionGate>{children}</SessionGate></QueryClientProvider>
}
