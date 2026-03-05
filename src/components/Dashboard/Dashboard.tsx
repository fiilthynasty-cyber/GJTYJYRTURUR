import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { Project, Lead } from '@/types'
import styles from './Dashboard.module.css'

export function Dashboard({ userId }: { userId: string }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(false)
  const [showNewProject, setShowNewProject] = useState(false)

  useEffect(() => {
    fetchProjects()
  }, [userId])

  useEffect(() => {
    if (selectedProject) {
      fetchLeads(selectedProject)
    }
  }, [selectedProject])

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const { data } = await supabase
        .from('projects')
        .select('*')
        .eq('owner_id', userId)
        .order('created_at', { ascending: false })

      if (data) {
        setProjects(data)
        if (data.length > 0 && !selectedProject) {
          setSelectedProject(data[0].id)
        }
      }
    } finally {
      setLoading(false)
    }
  }

  const fetchLeads = async (projectId: string) => {
    setLoading(true)
    try {
      const { data } = await supabase
        .from('leads')
        .select('*')
        .eq('project_id', projectId)
        .order('score', { ascending: false })

      if (data) {
        setLeads(data)
      }
    } finally {
      setLoading(false)
    }
  }

  const currentProject = projects.find(p => p.id === selectedProject)

  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <h1>FIILTHY</h1>
        <p>Lead Discovery Engine</p>
      </header>

      <div className={styles.container}>
        <aside className={styles.sidebar}>
          <div className={styles.projectsHeader}>
            <h2>Projects</h2>
            <button onClick={() => setShowNewProject(!showNewProject)} className={styles.addBtn}>
              +
            </button>
          </div>

          {showNewProject && (
            <ProjectForm
              userId={userId}
              onSuccess={() => {
                setShowNewProject(false)
                fetchProjects()
              }}
            />
          )}

          <div className={styles.projectsList}>
            {projects.map(project => (
              <button
                key={project.id}
                onClick={() => setSelectedProject(project.id)}
                className={`${styles.projectItem} ${selectedProject === project.id ? styles.active : ''}`}
              >
                {project.name}
              </button>
            ))}
          </div>
        </aside>

        <main className={styles.main}>
          {currentProject ? (
            <>
              <section className={styles.projectHeader}>
                <h2>{currentProject.name}</h2>
                <a href={currentProject.url} target="_blank" rel="noopener noreferrer" className={styles.url}>
                  {currentProject.url}
                </a>
              </section>

              <section className={styles.leads}>
                <h3>Leads ({leads.length})</h3>
                {loading ? (
                  <p className={styles.empty}>Loading...</p>
                ) : leads.length === 0 ? (
                  <p className={styles.empty}>No leads found. Run a scan to discover leads.</p>
                ) : (
                  <div className={styles.leadsList}>
                    {leads.map(lead => (
                      <article key={lead.id} className={styles.leadCard}>
                        <div className={styles.leadScore}>
                          <span className={`${styles.badge} ${styles[lead.intent]}`}>
                            {lead.intent}
                          </span>
                          <span className={styles.score}>{lead.score}</span>
                        </div>
                        <h4>{lead.title || 'Untitled'}</h4>
                        <p className={styles.source}>{lead.source}</p>
                        <p className={styles.content}>
                          {lead.content?.substring(0, 150)}...
                        </p>
                        <a href={lead.url} target="_blank" rel="noopener noreferrer" className={styles.leadUrl}>
                          View →
                        </a>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : (
            <div className={styles.empty}>
              <p>Create a project to get started</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function ProjectForm({ userId, onSuccess }: { userId: string; onSuccess: () => void }) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const { error: dbError } = await supabase
        .from('projects')
        .insert([{
          owner_id: userId,
          name,
          url,
          keywords: [],
          locations: [],
        }])

      if (dbError) throw dbError
      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className={styles.projectForm}>
      {error && <div className={styles.error}>{error}</div>}

      <input
        type="text"
        placeholder="Project name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        disabled={loading}
      />

      <input
        type="url"
        placeholder="Website URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        required
        disabled={loading}
      />

      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create'}
      </button>
    </form>
  )
}
