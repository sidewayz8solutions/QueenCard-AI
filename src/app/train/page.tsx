'use client'

import { createClient } from '@/lib/supabase/client'
import { apiClient } from '@/lib/api'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import type { User } from '@supabase/supabase-js'

export default function TrainPage() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [loraName, setLoraName] = useState('')
  const [triggerWord, setTriggerWord] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [trainingJobs, setTrainingJobs] = useState<Array<{id: string; status: string; progress: number; config: Record<string, unknown>}>>([])
  const [creating, setCreating] = useState(false)
  const [status, setStatus] = useState('')
  
  const router = useRouter()
  const supabase = createClient()

  const loadTrainingJobs = useCallback(async () => {
    try {
      const jobs = await apiClient.listTrainingJobs()
      setTrainingJobs(jobs)
    } catch (e) {
      console.error('Failed to load training jobs:', e)
    }
  }, [])

  useEffect(() => {
    const checkUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        router.push('/login')
        return
      }
      setUser(user)
      
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        apiClient.setToken(session.access_token)
      }
      
      await loadTrainingJobs()
      setLoading(false)
    }
    checkUser()
  }, [router, supabase.auth, loadTrainingJobs])

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setSelectedFiles(prev => [...prev, ...files])
    
    files.forEach(file => {
      setPreviews(prev => [...prev, URL.createObjectURL(file)])
    })
  }

  const removeImage = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
    setPreviews(prev => prev.filter((_, i) => i !== index))
  }

  const handleCreateTraining = async () => {
    if (!loraName || !triggerWord) {
      alert('Please enter LoRA name and trigger word')
      return
    }
    if (selectedFiles.length < 5) {
      alert('Please upload at least 5 training images')
      return
    }

    setCreating(true)
    setStatus('Creating training job...')

    try {
      const job = await apiClient.createTrainingJob({
        lora_name: loraName,
        trigger_word: triggerWord,
        training_type: 'lora',
        base_model: 'sd15',
      })

      setStatus('Uploading images...')
      
      // Upload each image
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i]
        setStatus(`Uploading image ${i + 1}/${selectedFiles.length}...`)
        
        const { put_url } = await apiClient.getUploadUrl(
          job.id,
          file.name,
          file.type,
          file.size
        )
        
        await fetch(put_url, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type },
        })
      }

      setStatus('Starting training...')
      await apiClient.startTraining(job.id)
      
      setStatus('Training started!')
      await loadTrainingJobs()
      
      // Reset form
      setLoraName('')
      setTriggerWord('')
      setSelectedFiles([])
      setPreviews([])
    } catch (error) {
      console.error('Training error:', error)
      setStatus(`Error: ${error instanceof Error ? error.message : 'Unknown'}`)
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-black to-pink-900">
      <header className="border-b border-purple-500/20 bg-black/50 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
            Train LoRA
          </h1>
          <div className="flex items-center gap-4">
            <a href="/generate" className="text-purple-400 hover:text-purple-300 text-sm">← Back to Generate</a>
            <span className="text-gray-400 text-sm">{user?.email}</span>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Create New Training */}
          <div className="bg-gray-900/80 backdrop-blur-sm rounded-xl p-6 border border-purple-500/20">
            <h2 className="text-xl font-semibold text-white mb-6">Create New LoRA</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-gray-400 text-sm mb-2">LoRA Name</label>
                <input
                  type="text"
                  value={loraName}
                  onChange={(e) => setLoraName(e.target.value)}
                  placeholder="my-custom-lora"
                  className="w-full bg-gray-800 text-white rounded-lg px-4 py-3 border border-gray-700 focus:border-purple-500 focus:outline-none"
                />
              </div>
              
              <div>
                <label className="block text-gray-400 text-sm mb-2">Trigger Word</label>
                <input
                  type="text"
                  value={triggerWord}
                  onChange={(e) => setTriggerWord(e.target.value)}
                  placeholder="sks person"
                  className="w-full bg-gray-800 text-white rounded-lg px-4 py-3 border border-gray-700 focus:border-purple-500 focus:outline-none"
                />
                <p className="text-gray-500 text-xs mt-1">Use this word in prompts to activate your LoRA</p>
              </div>

              <div>
                <label className="block text-gray-400 text-sm mb-2">
                  Training Images ({selectedFiles.length}/20 min: 5)
                </label>
                <label className="block">
                  <div className="border-2 border-dashed border-purple-500/30 rounded-lg p-4 text-center cursor-pointer hover:border-purple-500/50 transition">
                    <p className="text-gray-400 text-sm">Click to upload images</p>
                    <p className="text-gray-500 text-xs">High quality photos of your subject</p>
                  </div>
                  <input type="file" className="hidden" accept="image/*" multiple onChange={handleFilesChange} />
                </label>
                
                {previews.length > 0 && (
                  <div className="grid grid-cols-4 gap-2 mt-4">
                    {previews.map((preview, i) => (
                      <div key={i} className="relative group">
                        <img src={preview} alt="" className="w-full aspect-square object-cover rounded-lg" />
                        <button
                          onClick={() => removeImage(i)}
                          className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 text-xs opacity-0 group-hover:opacity-100 transition"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={handleCreateTraining}
                disabled={creating || selectedFiles.length < 5 || !loraName || !triggerWord}
                className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold py-3 rounded-lg hover:from-purple-500 hover:to-pink-500 transition disabled:opacity-50"
              >
                {creating ? 'Creating...' : '🚀 Start Training'}
              </button>

              {status && <p className="text-center text-gray-400 text-sm">{status}</p>}
            </div>
          </div>

          {/* Training Jobs */}
          <div className="bg-gray-900/80 backdrop-blur-sm rounded-xl p-6 border border-purple-500/20">
            <h2 className="text-xl font-semibold text-white mb-6">Your Training Jobs</h2>
            
            {trainingJobs.length > 0 ? (
              <div className="space-y-4">
                {trainingJobs.map(job => (
                  <div key={job.id} className="bg-gray-800/50 rounded-lg p-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="font-medium text-white">{String(job.config?.lora_name || 'Unnamed')}</h3>
                        <p className="text-gray-400 text-sm">Trigger: {String(job.config?.trigger_word || 'N/A')}</p>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs ${
                        job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                        job.status === 'processing' ? 'bg-yellow-500/20 text-yellow-400' :
                        job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {job.status}
                      </span>
                    </div>
                    {job.status === 'processing' && (
                      <div className="mt-3">
                        <div className="bg-gray-700 rounded-full h-2">
                          <div className="bg-purple-500 h-2 rounded-full transition-all" style={{width: `${job.progress}%`}} />
                        </div>
                        <p className="text-gray-400 text-xs mt-1">{job.progress}% complete</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">No training jobs yet</p>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

