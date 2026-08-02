import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useAuthStore } from '@/store/authStore'
import { apiClient } from '@/services/api'
import { Video, FileText, Trash2, ExternalLink } from 'lucide-react'

interface Project {
  video_id: string
  video_title: string
  filename: string
  created_at: string
  status: string
  has_transcription: boolean
  transcription_status?: string
}

export default function ProjectsPanel() {
  const { tokens } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProjects = async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get('/videos?per_page=50')
      const items = response.data.items || []
      const projectsData: Project[] = items.map((video: any) => ({
        video_id: video.id,
        video_title: video.title || video.original_filename,
        filename: video.filename,
        created_at: video.created_at,
        status: video.status,
        has_transcription: video.status === 'processed',
        transcription_status: video.status,
      }))
      setProjects(projectsData)
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to load projects')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleDelete = async (videoId: string) => {
    if (!confirm('Are you sure you want to delete this project?')) return
    try {
      await apiClient.delete(`/videos/${videoId}`)
      setProjects(projects.filter(p => p.video_id !== videoId))
    } catch (err: any) {
      alert(err.response?.data?.message || 'Failed to delete')
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'error' | 'processing' | 'warning'> = {
      processed: 'success',
      completed: 'success',
      processing: 'processing',
      uploaded: 'warning',
      failed: 'error',
    }
    return <Badge variant={variants[status] || 'default'}>{status}</Badge>
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-destructive mb-4">{error}</p>
          <Button onClick={fetchProjects} variant="outline">Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Projects</h2>
        <Button onClick={fetchProjects} variant="outline" size="sm">Refresh</Button>
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground mb-2">No projects yet</p>
            <p className="text-sm text-muted-foreground/60">Upload a video to get started</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <Card key={project.video_id} className="hover:border-primary/30 transition-colors">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Video className="w-5 h-5 text-primary" />
                </div>

                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate">{project.video_title}</h3>
                  <p className="text-xs text-muted-foreground">
                    {new Date(project.created_at).toLocaleDateString()} · {project.filename}
                  </p>
                </div>

                {getStatusBadge(project.status)}

                <div className="flex gap-2">
                  {project.has_transcription && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        navigator.clipboard.writeText(project.video_id)
                        alert('Video ID copied! Paste it in the Transcriptions tab.')
                      }}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(project.video_id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
