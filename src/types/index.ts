export interface User {
  id: string
  email: string
  plan: 'free' | 'pro' | 'enterprise'
  referral_code: string | null
  referral_count: number
  created_at: string
}

export interface Project {
  id: string
  owner_id: string
  name: string
  url: string
  niche: string | null
  keywords: string[]
  locations: string[]
  max_concurrent_jobs: number
  created_at: string
  updated_at: string
}

export interface Lead {
  id: string
  project_id: string
  url: string
  url_hash: string
  title: string | null
  content: string | null
  source: 'reddit' | 'hn' | 'serp' | string
  author: string | null
  score: number
  intent: 'high' | 'medium' | 'low'
  reasons: Record<string, unknown>
  status: 'new' | 'contacted' | 'converted' | 'ignored'
  created_at: string
  last_seen_at: string
}

export interface Job {
  id: string
  owner_id: string
  project_id: string | null
  type: string
  payload: Record<string, unknown>
  status: 'queued' | 'running' | 'completed' | 'failed'
  priority: number
  attempts: number
  created_at: string
}
