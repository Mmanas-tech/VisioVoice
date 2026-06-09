import React, { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { transcriptionService } from '@/services/transcription'
import { useUIStore } from '@/store/uiStore'
import { Download } from 'lucide-react'

type ExportFormat = 'json' | 'srt' | 'vtt'

interface ExportModalProps {
  transcriptionId: string
  isOpen: boolean
  onClose: () => void
}

const formats: { value: ExportFormat; label: string; description: string }[] = [
  { value: 'json', label: 'JSON', description: 'Structured data' },
  { value: 'srt', label: 'SRT', description: 'Subtitle file' },
  { value: 'vtt', label: 'VTT', description: 'WebVTT subtitles' },
]

export default function ExportModal({ transcriptionId, isOpen, onClose }: ExportModalProps) {
  const [selected, setSelected] = useState<ExportFormat[]>(['srt'])
  const [exporting, setExporting] = useState(false)
  const addToast = useUIStore((s) => s.addToast)

  const handleExport = async () => {
    setExporting(true)
    try {
      for (const format of selected) {
        const blob = await transcriptionService.exportTranscription(transcriptionId, format)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `transcription_${transcriptionId}.${format}`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
      addToast({ title: 'Export complete', variant: 'success' })
      onClose()
    } catch {
      addToast({ title: 'Export failed', variant: 'error' })
    } finally {
      setExporting(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export Transcription</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">Select format(s) to export</p>

          <div className="grid grid-cols-3 gap-3">
            {formats.map((f) => (
              <button
                key={f.value}
                onClick={() =>
                  setSelected((prev) =>
                    prev.includes(f.value) ? prev.filter((x) => x !== f.value) : [...prev, f.value]
                  )
                }
                className={`p-4 rounded-lg border-2 text-center transition-all ${
                  selected.includes(f.value)
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <p className="font-semibold">{f.label}</p>
                <p className="text-xs text-muted-foreground">{f.description}</p>
              </button>
            ))}
          </div>

          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={onClose} className="flex-1" disabled={exporting}>
              Cancel
            </Button>
            <Button onClick={handleExport} disabled={selected.length === 0 || exporting} className="flex-1">
              <Download className="w-4 h-4 mr-2" />
              {exporting ? 'Exporting...' : 'Export'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
