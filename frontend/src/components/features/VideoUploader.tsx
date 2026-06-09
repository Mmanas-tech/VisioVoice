import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { videoService } from '@/services/video'
import { transcriptionService } from '@/services/transcription'
import { useVideoStore } from '@/store/videoStore'
import { useUIStore } from '@/store/uiStore'
import { useNavigate } from 'react-router-dom'
import { Upload, FileVideo, CheckCircle, AlertCircle, Trash2 } from 'lucide-react'
import { formatFileSize } from '@/utils/formatters'
import { VIDEO_MAX_SIZE_MB, ALLOWED_VIDEO_MIME_TYPES } from '@/config/constants'

export default function VideoUploader() {
  const { uploads, addUpload, updateUpload, removeUpload } = useVideoStore()
  const addToast = useUIStore((s) => s.addToast)
  const navigate = useNavigate()
  const [videoList, setVideoList] = useState<Array<{ id: string; name: string; status: string }>>([])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      const uploadId = file.name
      addUpload({ fileName: file.name, progress: 0, status: 'pending' })

      try {
        const video = await videoService.uploadVideo(file, undefined, (progress) => {
          updateUpload(uploadId, { progress, status: 'uploading' })
        })

        updateUpload(uploadId, { progress: 100, status: 'completed', videoId: video.id })
        setVideoList((prev) => [...prev, { id: video.id, name: file.name, status: 'uploaded' }])

        addToast({ title: 'Upload complete', description: `${file.name} uploaded successfully`, variant: 'success' })
      } catch {
        updateUpload(uploadId, { status: 'error' })
        addToast({ title: 'Upload failed', description: `Failed to upload ${file.name}`, variant: 'error' })
      }
    }
  }, [addUpload, updateUpload, addToast])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: Object.fromEntries(ALLOWED_VIDEO_MIME_TYPES.map((t) => [t, []])),
    maxSize: VIDEO_MAX_SIZE_MB * 1024 * 1024,
  })

  const startTranscription = async (videoId: string) => {
    try {
      const job = await transcriptionService.startTranscription(videoId)
      addToast({ title: 'Transcription started', description: `Job ${job.job_id}`, variant: 'success' })
      navigate('/dashboard')
    } catch {
      addToast({ title: 'Error', description: 'Failed to start transcription', variant: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Upload Video</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all duration-300 ${
              isDragActive ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-semibold mb-2">
              {isDragActive ? 'Drop video here' : 'Drag & drop video or click to select'}
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              Supported: MP4, MOV, AVI, MKV (Max 2GB)
            </p>
            <Button>Select File</Button>
          </div>

          {uploads.length > 0 && (
            <div className="mt-8 space-y-4">
              {uploads.map((upload) => (
                <div key={upload.fileName} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <FileVideo className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{upload.fileName}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={upload.status === 'completed' ? 'success' : upload.status === 'error' ? 'error' : 'processing'}>
                        {upload.status === 'completed' ? (
                          <CheckCircle className="w-3 h-3 mr-1" />
                        ) : upload.status === 'error' ? (
                          <AlertCircle className="w-3 h-3 mr-1" />
                        ) : null}
                        {upload.status}
                      </Badge>
                      {upload.status === 'completed' && upload.videoId && (
                        <Button size="sm" onClick={() => startTranscription(upload.videoId!)}>
                          Transcribe
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-primary h-full transition-all duration-300"
                      style={{ width: `${upload.progress}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {videoList.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Uploaded Videos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {videoList.map((v) => (
                <div key={v.id} className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50">
                  <div className="flex items-center gap-3">
                    <FileVideo className="w-5 h-5 text-primary" />
                    <span className="text-sm">{v.name}</span>
                    <Badge variant="success">Ready</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => startTranscription(v.id)}>
                      Transcribe
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setVideoList((prev) => prev.filter((x) => x.id !== v.id))}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
