import React, { useEffect, useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { transcriptionService } from '@/services/transcription'
import { useTranscriptionStore } from '@/store/transcriptionStore'
import { useUIStore } from '@/store/uiStore'
import { formatTime, formatPercentage } from '@/utils/formatters'
import { getSocket, joinTranscription, leaveTranscription, onTranscriptionProgress, onTranscriptionComplete } from '@/services/socket'
import { FileText, Download, Trash2, RefreshCw } from 'lucide-react'
import ExportModal from './ExportModal'

export default function TranscriptionViewer() {
  const { currentTranscription, setCurrentTranscription, setIsLoading, isLoading } = useTranscriptionStore()
  const addToast = useUIStore((s) => s.addToast)
  const [videoId, setVideoId] = useState('')
  const [transcriptionId, setTranscriptionId] = useState('')
  const [progress, setProgress] = useState(0)
  const [showExport, setShowExport] = useState(false)
  const cleanupRefs = useRef<(() => void)[]>([])

  const fetchTranscription = async () => {
    if (!transcriptionId.trim()) return
    setIsLoading(true)
    try {
      const data = await transcriptionService.getTranscription(transcriptionId)
      setCurrentTranscription(data)
      setProgress(data.progress)
    } catch {
      addToast({ title: 'Error', description: 'Failed to fetch transcription', variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!transcriptionId) return

    const socket = getSocket()
    joinTranscription(transcriptionId)

    const unsubProgress = onTranscriptionProgress((data) => {
      if (data.transcription_id === transcriptionId) {
        setProgress(data.progress)
      }
    })

    const unsubComplete = onTranscriptionComplete((data) => {
      if (data.transcription_id === transcriptionId) {
        fetchTranscription()
      }
    })

    cleanupRefs.current.push(unsubProgress, unsubComplete)

    return () => {
      leaveTranscription(transcriptionId)
      cleanupRefs.current.forEach((fn) => fn())
      cleanupRefs.current = []
    }
  }, [transcriptionId])

  const handleDelete = async () => {
    if (!currentTranscription) return
    try {
      await transcriptionService.deleteTranscription(currentTranscription.id)
      setCurrentTranscription(null)
      setTranscriptionId('')
      addToast({ title: 'Deleted', description: 'Transcription deleted', variant: 'success' })
    } catch {
      addToast({ title: 'Error', description: 'Failed to delete', variant: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Transcription Viewer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <input
              placeholder="Enter transcription ID"
              value={transcriptionId}
              onChange={(e) => setTranscriptionId(e.target.value)}
              className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <Button onClick={fetchTranscription} disabled={!transcriptionId.trim() || isLoading}>
              {isLoading ? <Spinner size="sm" /> : 'Load'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {currentTranscription && (
        <>
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Transcription Status</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      currentTranscription.status === 'completed'
                        ? 'success'
                        : currentTranscription.status === 'failed'
                        ? 'error'
                        : 'processing'
                    }
                  >
                    {currentTranscription.status}
                  </Badge>
                  <Button size="sm" variant="ghost" onClick={() => setShowExport(true)}>
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleDelete}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {currentTranscription.status === 'processing' && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <span>Processing...</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
                    <div className="bg-primary h-full transition-all duration-500" style={{ width: `${progress}%` }} />
                  </div>
                </div>
              )}

              {currentTranscription.status === 'completed' && (
                <div className="space-y-4">
                  <div className="flex gap-6">
                    <div>
                      <p className="text-sm text-muted-foreground">Confidence</p>
                      <p className="text-2xl font-bold text-primary">
                        {currentTranscription.confidence_score != null
                          ? formatPercentage(currentTranscription.confidence_score)
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Segments</p>
                      <p className="text-2xl font-bold">{currentTranscription.segments.length}</p>
                    </div>
                    {currentTranscription.processing_time_seconds != null && (
                      <div>
                        <p className="text-sm text-muted-foreground">Processing Time</p>
                        <p className="text-2xl font-bold">{currentTranscription.processing_time_seconds.toFixed(1)}s</p>
                      </div>
                    )}
                  </div>

                  {currentTranscription.raw_transcript && (
                    <div className="bg-secondary/50 rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-2">Raw Transcription</p>
                      <p className="text-foreground leading-relaxed">{currentTranscription.raw_transcript}</p>
                    </div>
                  )}

                  {currentTranscription.cleaned_transcript && (
                    <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-2">Refined Transcription</p>
                      <p className="text-foreground leading-relaxed">{currentTranscription.cleaned_transcript}</p>
                    </div>
                  )}
                </div>
              )}

              {currentTranscription.status === 'failed' && (
                <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
                  <p className="font-semibold text-destructive">Processing Failed</p>
                  <p className="text-sm text-muted-foreground mt-2">{currentTranscription.error_message}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {currentTranscription.segments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Segments Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {currentTranscription.segments.map((seg) => (
                    <div key={seg.id} className="flex gap-4 p-3 rounded-lg hover:bg-secondary/50 transition-colors">
                      <div className="text-sm text-muted-foreground flex-shrink-0 w-24 font-mono">
                        {formatTime(seg.start_time_ms)} → {formatTime(seg.end_time_ms)}
                      </div>
                      <div className="flex-1">
                        <p className="text-foreground">{seg.text}</p>
                        {seg.confidence_score != null && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Confidence: {formatPercentage(seg.confidence_score)}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {showExport && currentTranscription && (
        <ExportModal
          transcriptionId={currentTranscription.id}
          isOpen={showExport}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  )
}
