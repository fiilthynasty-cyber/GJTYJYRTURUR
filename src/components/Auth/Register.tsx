import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import styles from './Auth.module.css'

interface RegisterProps {
  onSuccess: () => void
}

export function Register({ onSuccess }: RegisterProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const { data: { user }, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
      })

      if (signUpError) throw signUpError

      if (user) {
        const { error: dbError } = await supabase
          .from('users')
          .insert([{
            id: user.id,
            email: user.email,
            plan: 'free',
          }])

        if (dbError) throw dbError
      }

      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleRegister} className={styles.form}>
      <h2>Create Account</h2>
      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.field}>
        <label>Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <div className={styles.field}>
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={loading}
        />
      </div>

      <button type="submit" disabled={loading} className={styles.button}>
        {loading ? 'Creating account...' : 'Sign Up'}
      </button>
    </form>
  )
}
