import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { audioService } from '@/services/audio'
import { useUIStore } from '@/store/uiStore'
import { Mic, Download, Music } from 'lucide-react'

export default function AudioPanel() {
  const [transcriptionId, setTranscriptionId] = useState('')
  const [ttsBackend, setTtsBackend] = useState('pyttsx3')
  const [isSynthesizing, setIsSynthesizing] = useState(false)
  const [synthesisResult, setSynthesisResult] = useState<Record<string, string> | null>(null)
  const addToast = useUIStore((s) => s.addToast)

  const handleSynthesize = async () => {
    if (!transcriptionId.trim()) return
    setIsSynthesizing(true)
    try {
      await audioService.requestSynthesis(transcriptionId, { ttsBackend })
      addToast({ title: 'Synthesis started', variant: 'success' })

      const pollInterval = setInterval(async () => {
        try {
          const status = await audioService.getSynthesisStatus(transcriptionId)
          if (status.status === 'completed') {
            clearInterval(pollInterval)
            setSynthesisResult(status.audio_files)
            setIsSynthesizing(false)
            addToast({ title: 'Audio synthesis complete', variant: 'success' })
          } else if (status.status === 'failed') {
            clearInterval(pollInterval)
            setIsSynthesizing(false)
            addToast({ title: 'Synthesis failed', variant: 'error' })
          }
        } catch {}
      }, 3000)
    } catch {
      setIsSynthesizing(false)
      addToast({ title: 'Error', description: 'Failed to start synthesis', variant: 'error' })
    }
  }

  const downloadAudio = async (format: string) => {
    try {
      const blob = await audioService.downloadAudio(transcriptionId, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `synthesized_${transcriptionId}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      addToast({ title: 'Download failed', variant: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mic className="w-5 h-5 text-primary" />
            Audio Synthesis
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            label="Transcription ID"
            placeholder="Enter transcription ID"
            value={transcriptionId}
            onChange={(e) => setTranscriptionId(e.target.value)}
          />

          <div>
            <label className="text-sm font-medium text-foreground block mb-2">TTS Backend</label>
            <div className="flex gap-2">
              {['pyttsx3', 'google', 'bark'].map((b) => (
                <button
                  key={b}
                  onClick={() => setTtsBackend(b)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    ttsBackend === b ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground hover:bg-muted'
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>
          </div>

          <Button onClick={handleSynthesize} disabled={!transcriptionId.trim() || isSynthesizing}>
            {isSynthesizing ? 'Synthesizing...' : 'Start Synthesis'}
          </Button>
        </CardContent>
      </Card>

      {synthesisResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Music className="w-5 h-5 text-primary" />
              Generated Audio
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(synthesisResult).map(([format, path]) => (
                <div key={format} className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50">
                  <div className="flex items-center gap-3">
                    <Music className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium uppercase">{format}</span>
                    <Badge variant="success">Ready</Badge>
                  </div>
                  <Button size="sm" onClick={() => downloadAudio(format)}>
                    <Download className="w-4 h-4 mr-1" /> Download
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
