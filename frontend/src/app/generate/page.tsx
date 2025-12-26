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
  const [activeTab, setActiveTab] = useState<TabType>('img2vid')
  const [prompt, setPrompt] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')
  const [outputUrl, setOutputUrl] = useState<string | null>(null)
  const [outputType, setOutputType] = useState<'image' | 'video'>('video')

  // LoRA selection
  const [loras, setLoras] = useState<LoRA[]>([])
  const [selectedLoras, setSelectedLoras] = useState<string[]>([])
  const [showLoraModal, setShowLoraModal] = useState(false)

  // Video params
  const [motionStrength, setMotionStrength] = useState(127)
  const [numFrames, setNumFrames] = useState(81)

  const router = useRouter()
  const supabase = useMemo(() => createClient(), [])

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

      try {
        const loraList = await apiClient.listLoras({ is_nsfw: true })
        setLoras(loraList)
      } catch (e) {
        console.error('Failed to load LoRAs:', e)
      }

      setLoading(false)
    }
    checkUser()
    return () => {
      unmountedRef.current = true
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current)
    }
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
    const maxAttempts = 120

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
    if (!selectedFile && activeTab === 'img2vid') {
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
        params.fps = 16
        // 720p resolution for Wan 2.1 14B model
        params.width = 1280
        params.height = 720
      }

      const { job_id } = await apiClient.createJob({
        prompt,
        job_type: jobType,
        model_name: jobType === 'img2vid' ? 'wan-i2v-720p' : 'realistic-vision-v5',
        lora_names: selectedLoras,
        params,
      })
      setStatus('Uploading...')

      if (selectedFile) {
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
      }
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
        <div className="neon-pulse rounded-full h-12 w-12 border-2 border-[#e0ff00]" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black">
      {/* Background glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-[#e0ff00] opacity-[0.03] blur-[100px] rounded-full" />
      </div>

      {/* Header */}
      <header className="border-b border-[#e0ff00]/20 bg-black/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold neon-text">
            QueenCard
          </h1>
          <div className="flex items-center gap-6">
            <span className="text-[#e0ff00]/50 text-sm">{user?.email}</span>
            <button onClick={handleLogout} className="text-[#e0ff00]/70 hover:text-[#e0ff00] text-sm transition">
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-6xl mx-auto px-4 pt-6">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('img2vid')}
            className={`px-6 py-3 rounded-t-lg font-medium transition ${
              activeTab === 'img2vid'
                ? 'bg-black text-[#e0ff00] border-t border-l border-r border-[#e0ff00]/50 neon-text-sm'
                : 'bg-black/50 text-[#e0ff00]/40 hover:text-[#e0ff00]/70 border border-transparent'
            }`}
          >
            🎬 Image to Video
          </button>
          <button
            onClick={() => setActiveTab('img2img')}
            className={`px-6 py-3 rounded-t-lg font-medium transition ${
              activeTab === 'img2img'
                ? 'bg-black text-[#e0ff00] border-t border-l border-r border-[#e0ff00]/50 neon-text-sm'
                : 'bg-black/50 text-[#e0ff00]/40 hover:text-[#e0ff00]/70 border border-transparent'
            }`}
          >
            🖼️ Image to Image
          </button>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 pb-8">
        <div className="grid md:grid-cols-2 gap-8 neon-card rounded-b-xl rounded-tr-xl p-6">
          {/* Input Section */}
          <div className="space-y-6">
            {/* Upload */}
            <div>
              <h2 className="text-lg font-semibold text-[#e0ff00] mb-3">Upload Image</h2>
              <label className="block">
                <div className="border-2 border-dashed border-[#e0ff00]/30 rounded-lg p-6 text-center cursor-pointer hover:border-[#e0ff00]/60 transition">
                  {preview ? (
                    <img src={preview} alt="Preview" className="max-h-48 mx-auto rounded-lg" />
                  ) : (
                    <div className="text-[#e0ff00]/50">
                      <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-sm">Click to upload</p>
                    </div>
                  )}
                </div>
                <input type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
              </label>
            </div>

            {/* Prompt */}
            <div>
              <h2 className="text-lg font-semibold text-[#e0ff00] mb-3">Prompt</h2>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={activeTab === 'img2vid' ? 'Describe the motion... (e.g., she moans and moves her hips)' : 'Describe the transformation...'}
                className="neon-input w-full h-24 rounded-lg p-3 resize-none text-sm"
              />
            </div>

            {/* LoRA Selection */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <h2 className="text-lg font-semibold text-[#e0ff00]">LoRAs</h2>
                <button onClick={() => setShowLoraModal(true)} className="text-[#e0ff00]/70 hover:text-[#e0ff00] text-sm transition">
                  + Browse LoRAs
                </button>
              </div>
              {selectedLoras.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {selectedLoras.map(slug => (
                    <span key={slug} className="bg-[#e0ff00]/10 text-[#e0ff00] px-3 py-1 rounded-full text-sm flex items-center gap-2 border border-[#e0ff00]/30">
                      {slug}
                      <button onClick={() => toggleLora(slug)} className="hover:text-white">×</button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-[#e0ff00]/30 text-sm">No LoRAs selected</p>
              )}
            </div>

            {/* Video Settings */}
            {activeTab === 'img2vid' && (
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-[#e0ff00]/70 mb-2 block">Motion Strength: {motionStrength}</label>
                  <input
                    type="range"
                    min="1"
                    max="255"
                    value={motionStrength}
                    onChange={(e) => setMotionStrength(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="text-sm text-[#e0ff00]/70 mb-2 block">Frames: {numFrames}</label>
                  <input
                    type="range"
                    min="25"
                    max="129"
                    step="8"
                    value={numFrames}
                    onChange={(e) => setNumFrames(Number(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={generating || !selectedFile}
              className="neon-button-solid w-full py-4 rounded-lg text-lg disabled:opacity-50"
            >
              {generating ? '⚡ Generating...' : activeTab === 'img2vid' ? '🎬 Generate Video' : '✨ Generate Image'}
            </button>

            {status && (
              <div className="text-center text-[#e0ff00]/70 text-sm">
                <span className="inline-block animate-pulse">●</span> {status}
              </div>
            )}
          </div>

          {/* Output Section */}
          <div>
            <h2 className="text-lg font-semibold text-[#e0ff00] mb-3">Result</h2>
            <div className="aspect-square bg-black rounded-lg flex items-center justify-center overflow-hidden border border-[#e0ff00]/20">
              {outputUrl ? (
                outputType === 'video' ? (
                  <video src={outputUrl} controls autoPlay loop className="max-w-full max-h-full rounded-lg" />
                ) : (
                  <img src={outputUrl} alt="Generated" className="max-w-full max-h-full rounded-lg" />
                )
              ) : (
                <div className="text-[#e0ff00]/30 text-center">
                  <p className="text-4xl mb-2">{activeTab === 'img2vid' ? '🎬' : '🖼️'}</p>
                  <p>Output will appear here</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* LoRA Modal */}
      {showLoraModal && (
        <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4">
          <div className="neon-card rounded-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-4 border-b border-[#e0ff00]/20 flex justify-between items-center">
              <h3 className="text-xl font-semibold text-[#e0ff00]">Browse LoRAs</h3>
              <button onClick={() => setShowLoraModal(false)} className="text-[#e0ff00]/50 hover:text-[#e0ff00] text-2xl">×</button>
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
                          ? 'border-[#e0ff00] bg-[#e0ff00]/10'
                          : 'border-[#e0ff00]/20 hover:border-[#e0ff00]/50'
                      }`}
                    >
                      <h4 className="font-medium text-[#e0ff00]">{lora.name}</h4>
                      <p className="text-[#e0ff00]/50 text-sm mt-1">{lora.description || lora.category}</p>
                      {lora.trigger_words.length > 0 && (
                        <p className="text-[#e0ff00]/70 text-xs mt-2">Trigger: {lora.trigger_words.join(', ')}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[#e0ff00]/40 text-center py-8">No LoRAs available yet</p>
              )}
            </div>
            <div className="p-4 border-t border-[#e0ff00]/20">
              <button onClick={() => setShowLoraModal(false)} className="neon-button-solid w-full py-2 rounded-lg">
                Done ({selectedLoras.length} selected)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
