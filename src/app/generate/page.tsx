'use client'

import { createClient } from '@/lib/supabase/client'
import { apiClient, LoRA } from '@/lib/api'
import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import type { User } from '@supabase/supabase-js'

type TabType = 'img2img' | 'img2vid'

export default function GeneratePage() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>('img2img')
  const [prompt, setPrompt] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')
  const [outputUrl, setOutputUrl] = useState<string | null>(null)
  const [outputType, setOutputType] = useState<'image' | 'video'>('image')

  // LoRA selection
  const [loras, setLoras] = useState<LoRA[]>([])
  const [selectedLoras, setSelectedLoras] = useState<string[]>([])
  const [showLoraModal, setShowLoraModal] = useState(false)

  // Video params
  const [motionStrength, setMotionStrength] = useState(127)
  const [numFrames, setNumFrames] = useState(25)

  const router = useRouter()
  // Create a stable Supabase client that won't change across renders/HMR
  const supabase = useMemo(() => createClient(), [])

  // Guard against HMR/StrictMode double-invocations and component unmounts
  const unmountedRef = useRef(false)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollingRef = useRef(false)

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

      // Load LoRAs
      try {
        const loraList = await apiClient.listLoras({ is_nsfw: true })
        setLoras(loraList)
      } catch (e) {
        console.error('Failed to load LoRAs:', e)
      }

      setLoading(false)
    }
    checkUser()
    // Cleanup on unmount (HMR/route change)
    return () => {
      unmountedRef.current = true
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current)
    }
  // Intentionally run once on mount to avoid HMR-induced loops
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setPreview(URL.createObjectURL(file))
    }
  }

  const pollRunpodStatus = useCallback(async (jobId: string, runpodJobId: string, jobType: string) => {
    if (pollingRef.current) return
    pollingRef.current = true

    let attempts = 0
    const maxAttempts = 120 // 10 minutes for video

    const poll = async () => {
      if (unmountedRef.current) return
      try {
        const rpStatus = await apiClient.getRunpodStatus(jobId, runpodJobId)
        setStatus(`Processing: ${rpStatus.status}`)

        if (rpStatus.status === 'COMPLETED') {
          const job = await apiClient.getJobStatus(jobId)
          if (job.output_urls?.length > 0) {
            const { get_url } = await apiClient.getDownloadUrl(job.output_urls[0].key)
            setOutputUrl(get_url)
            setOutputType(jobType === 'img2vid' ? 'video' : 'image')
          }
          setGenerating(false)
          setStatus('Complete!')
          pollingRef.current = false
          return
        }

        if (rpStatus.status === 'FAILED') {
          setStatus('Generation failed')
          setGenerating(false)
          pollingRef.current = false
          return
        }

        attempts++
        if (attempts < maxAttempts) {
          pollTimeoutRef.current = setTimeout(poll, 5000)
        } else {
          setStatus('Timeout')
          setGenerating(false)
          pollingRef.current = false
        }
      } catch (error) {
        console.error('Polling error:', error)
        setStatus('Error')
        setGenerating(false)
        pollingRef.current = false
      }
    }

    poll()
  }, [])

  const handleGenerate = async () => {
    if (!selectedFile) {
      alert('Please select an image')
      return
    }

    setGenerating(true)
    setOutputUrl(null)
    setStatus('Creating job...')

    try {
      const jobType = activeTab
      const params: Record<string, unknown> = {}

      if (jobType === 'img2vid') {
        params.motion_bucket_id = motionStrength
        params.num_frames = numFrames
        params.fps = 7
      }

      const { job_id } = await apiClient.createJob({
        prompt,
        job_type: jobType,
        model_name: jobType === 'img2vid' ? 'svd' : 'realistic-vision-v5',
        lora_names: selectedLoras,
        params,
      })
      setStatus('Uploading...')

      const { put_url } = await apiClient.getUploadUrl(
        job_id,
        selectedFile.name,
        selectedFile.type,
        selectedFile.size
      )

      await fetch(put_url, {
        method: 'PUT',
        body: selectedFile,
        headers: { 'Content-Type': selectedFile.type },
      })
      setStatus('Sending to GPU...')

      const { runpod_job_id } = await apiClient.dispatchJob(job_id)
      setStatus('Processing...')

      pollRunpodStatus(job_id, runpod_job_id, jobType)
    } catch (error) {
      console.error('Generation error:', error)
      setStatus(`Error: ${error instanceof Error ? error.message : 'Unknown'}`)
      setGenerating(false)
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  const toggleLora = (slug: string) => {
    setSelectedLoras(prev =>
      prev.includes(slug) ? prev.filter(l => l !== slug) : [...prev, slug]
    )
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
      {/* Header */}
      <header className="border-b border-purple-500/20 bg-black/50 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
            QueenCard AI
          </h1>
          <div className="flex items-center gap-4">
            <a href="/train" className="text-purple-400 hover:text-purple-300 text-sm">Train Model</a>
            <span className="text-gray-400 text-sm">{user?.email}</span>
            <button onClick={handleLogout} className="text-gray-400 hover:text-white text-sm">Logout</button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-6xl mx-auto px-4 pt-6">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('img2img')}
            className={`px-6 py-3 rounded-t-lg font-medium transition ${
              activeTab === 'img2img'
                ? 'bg-gray-900/80 text-white border-t border-l border-r border-purple-500/30'
                : 'bg-gray-800/50 text-gray-400 hover:text-white'
            }`}
          >
            🖼️ Image to Image
          </button>
          <button
            onClick={() => setActiveTab('img2vid')}
            className={`px-6 py-3 rounded-t-lg font-medium transition ${
              activeTab === 'img2vid'
                ? 'bg-gray-900/80 text-white border-t border-l border-r border-purple-500/30'
                : 'bg-gray-800/50 text-gray-400 hover:text-white'
            }`}
          >
            🎬 Image to Video
          </button>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 pb-8">
        <div className="grid md:grid-cols-2 gap-8 bg-gray-900/80 backdrop-blur-sm rounded-b-xl rounded-tr-xl p-6 border border-purple-500/20">
          {/* Input Section */}
          <div className="space-y-6">
            {/* Upload */}
            <div>
              <h2 className="text-lg font-semibold text-white mb-3">Upload Image</h2>
              <label className="block">
                <div className="border-2 border-dashed border-purple-500/30 rounded-lg p-6 text-center cursor-pointer hover:border-purple-500/50 transition">
                  {preview ? (
                    <img src={preview} alt="Preview" className="max-h-48 mx-auto rounded-lg" />
                  ) : (
                    <div className="text-gray-400">
                      <svg className="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-sm">Click to upload</p>
                    </div>
                  )}
                </div>
                <input type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
              </label>
            </div>

            {/* Prompt (only for img2img) */}
            {activeTab === 'img2img' && (
              <div>
                <h2 className="text-lg font-semibold text-white mb-3">Prompt</h2>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the transformation..."
                  className="w-full h-24 bg-gray-800 text-white rounded-lg p-3 border border-gray-700 focus:border-purple-500 focus:outline-none resize-none text-sm"
                />
              </div>
            )}

            {/* LoRA Selection (only for img2img) */}
            {activeTab === 'img2img' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h2 className="text-lg font-semibold text-white">LoRAs</h2>
                  <button onClick={() => setShowLoraModal(true)} className="text-purple-400 hover:text-purple-300 text-sm">
                    + Browse LoRAs
                  </button>
                </div>
                {selectedLoras.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedLoras.map(slug => (
                      <span key={slug} className="bg-purple-600/30 text-purple-300 px-3 py-1 rounded-full text-sm flex items-center gap-2">
                        {slug}
                        <button onClick={() => toggleLora(slug)} className="hover:text-white">×</button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">No LoRAs selected</p>
                )}
              </div>
            )}

            {/* Video Settings (only for img2vid) */}
            {activeTab === 'img2vid' && (
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Motion Strength: {motionStrength}</label>
                  <input
                    type="range"
                    min="1"
                    max="255"
                    value={motionStrength}
                    onChange={(e) => setMotionStrength(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Frames: {numFrames}</label>
                  <input
                    type="range"
                    min="14"
                    max="50"
                    value={numFrames}
                    onChange={(e) => setNumFrames(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                </div>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={generating || !selectedFile || (activeTab === 'img2img' && !prompt)}
              className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold py-4 rounded-lg hover:from-purple-500 hover:to-pink-500 transition disabled:opacity-50"
            >
              {generating ? 'Generating...' : activeTab === 'img2vid' ? '🎬 Generate Video' : '✨ Generate Image'}
            </button>

            {status && <div className="text-center text-gray-400 animate-pulse text-sm">{status}</div>}
          </div>

          {/* Output Section */}
          <div>
            <h2 className="text-lg font-semibold text-white mb-3">Result</h2>
            <div className="aspect-square bg-gray-800 rounded-lg flex items-center justify-center overflow-hidden">
              {outputUrl ? (
                outputType === 'video' ? (
                  <video src={outputUrl} controls autoPlay loop className="max-w-full max-h-full rounded-lg" />
                ) : (
                  <img src={outputUrl} alt="Generated" className="max-w-full max-h-full rounded-lg" />
                )
              ) : (
                <div className="text-gray-500 text-center">
                  <p>{activeTab === 'img2vid' ? '🎬 Video' : '🖼️ Image'} will appear here</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* LoRA Modal */}
      {showLoraModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden border border-purple-500/30">
            <div className="p-4 border-b border-gray-800 flex justify-between items-center">
              <h3 className="text-xl font-semibold text-white">Browse LoRAs</h3>
              <button onClick={() => setShowLoraModal(false)} className="text-gray-400 hover:text-white text-2xl">×</button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {loras.length > 0 ? (
                <div className="grid grid-cols-2 gap-4">
                  {loras.map(lora => (
                    <div
                      key={lora.id}
                      onClick={() => toggleLora(lora.slug)}
                      className={`p-4 rounded-lg cursor-pointer border transition ${
                        selectedLoras.includes(lora.slug)
                          ? 'border-purple-500 bg-purple-500/20'
                          : 'border-gray-700 hover:border-gray-600'
                      }`}
                    >
                      <h4 className="font-medium text-white">{lora.name}</h4>
                      <p className="text-gray-400 text-sm mt-1">{lora.description || lora.category}</p>
                      {lora.trigger_words.length > 0 && (
                        <p className="text-purple-400 text-xs mt-2">Trigger: {lora.trigger_words.join(', ')}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-center py-8">No LoRAs available yet</p>
              )}
            </div>
            <div className="p-4 border-t border-gray-800">
              <button onClick={() => setShowLoraModal(false)} className="w-full bg-purple-600 text-white py-2 rounded-lg">
                Done ({selectedLoras.length} selected)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

