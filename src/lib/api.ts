const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

export interface LoRA {
  id: string
  name: string
  slug: string
  description?: string
  preview_url?: string
  category: string
  tags: string[]
  trigger_words: string[]
  base_model: string
  is_nsfw: boolean
  download_count: number
}

export interface BaseModel {
  id: string
  name: string
  slug: string
  description?: string
  hf_repo: string
  model_type: string
  is_nsfw: boolean
}

export class ApiClient {
  private token: string | null = null

  setToken(token: string | null) {
    this.token = token
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${res.status}`)
    }

    return res.json()
  }

  // Jobs
  async createJob(data: {
    prompt?: string
    job_type?: string
    model_name?: string
    lora_names?: string[]
    params?: Record<string, unknown>
  }) {
    return this.request<{ job_id: string; status: string; job_type: string }>('/jobs/create', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async dispatchJob(jobId: string) {
    return this.request<{ runpod_job_id: string; status: string }>(`/jobs/${jobId}/dispatch`, {
      method: 'POST',
    })
  }

  async getJobStatus(jobId: string) {
    return this.request<{
      id: string
      status: string
      job_type: string
      prompt: string
      model_name: string
      lora_names: string[]
      input_urls: Array<{ key: string; mime: string; bytes: number }>
      output_urls: Array<{ key: string; type?: string }>
      error: string | null
    }>(`/jobs/${jobId}/status`)
  }

  async getRunpodStatus(jobId: string, runpodJobId: string) {
    return this.request<{ status: string; output?: unknown }>(`/jobs/${jobId}/runpod-status?runpod_job_id=${runpodJobId}`)
  }

  // Storage
  async getUploadUrl(jobId: string, filename: string, mime: string, bytes: number) {
    return this.request<{ key: string; put_url: string }>('/storage/upload-url', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, filename, mime, bytes }),
    })
  }

  async getDownloadUrl(key: string) {
    return this.request<{ get_url: string }>('/storage/download-url', {
      method: 'POST',
      body: JSON.stringify({ key }),
    })
  }

  // LoRAs
  async listLoras(params?: { category?: string; is_nsfw?: boolean; search?: string }) {
    const query = new URLSearchParams()
    if (params?.category) query.set('category', params.category)
    if (params?.is_nsfw !== undefined) query.set('is_nsfw', String(params.is_nsfw))
    if (params?.search) query.set('search', params.search)
    return this.request<LoRA[]>(`/loras?${query}`)
  }

  async getLoraCategories() {
    return this.request<Array<{ slug: string; name: string; description: string }>>('/loras/categories')
  }

  // Models
  async listModels(modelType?: string) {
    const query = modelType ? `?model_type=${modelType}` : ''
    return this.request<BaseModel[]>(`/models${query}`)
  }

  // Training
  async createTrainingJob(data: {
    training_type?: string
    base_model?: string
    lora_name: string
    trigger_word: string
    config?: Record<string, unknown>
  }) {
    return this.request<{ id: string; status: string }>('/training/create', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async listTrainingJobs() {
    return this.request<Array<{
      id: string
      status: string
      training_type: string
      progress: number
      config: Record<string, unknown>
    }>>('/training')
  }

  async startTraining(jobId: string) {
    return this.request<{ status: string }>(`/training/${jobId}/start`, {
      method: 'POST',
    })
  }
}

export const apiClient = new ApiClient()

