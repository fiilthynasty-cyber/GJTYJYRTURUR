import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Login } from '@/components/Auth/Login'
import { Register } from '@/components/Auth/Register'
import { Dashboard } from '@/components/Dashboard/Dashboard'
import { supabase } from '@/lib/supabase'
import styles from './App.module.css'

function App() {
  const { user, loading } = useAuth()
  const [showRegister, setShowRegister] = useState(false)

  if (loading) {
    return <div className={styles.loading}>Loading...</div>
  }

  if (!user) {
    return (
      <div className={styles.authContainer}>
        {showRegister ? (
          <>
            <Register onSuccess={() => setShowRegister(false)} />
            <p className={styles.toggle}>
              Already have an account?{' '}
              <button onClick={() => setShowRegister(false)}>Sign in</button>
            </p>
          </>
        ) : (
          <>
            <Login onSuccess={() => {}} />
            <p className={styles.toggle}>
              Don't have an account?{' '}
              <button onClick={() => setShowRegister(true)}>Create one</button>
            </p>
          </>
        )}
      </div>
    )
  }

  return (
    <div className={styles.app}>
      <Dashboard userId={user.id} />
      <button
        onClick={() => supabase.auth.signOut()}
        className={styles.logout}
        title="Sign out"
      >
        Sign Out
      </button>
    </div>
  )
}

export default App
