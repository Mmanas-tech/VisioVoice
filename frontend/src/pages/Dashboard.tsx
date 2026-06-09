import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import VideoUploader from '@/components/features/VideoUploader'
import TranscriptionViewer from '@/components/features/TranscriptionViewer'
import AudioPanel from '@/components/features/AudioPanel'
import { useUIStore } from '@/store/uiStore'
import { ToastContainer } from '@/components/ui/Toast'

export default function Dashboard() {
  const { activeTab, setActiveTab } = useUIStore()

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <ToastContainer />

      <div className="flex pt-16">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 p-6 md:p-10">
          {activeTab === 'upload' && <VideoUploader />}
          {activeTab === 'transcriptions' && <TranscriptionViewer />}
          {activeTab === 'audio' && <AudioPanel />}
          {activeTab === 'projects' && <ProjectsPlaceholder />}
          {activeTab === 'settings' && <SettingsPlaceholder />}
        </main>
      </div>
    </div>
  )
}

function ProjectsPlaceholder() {
  return (
    <div className="text-center py-20">
      <h2 className="text-2xl font-bold mb-4">Projects</h2>
      <p className="text-muted-foreground">Your saved projects will appear here.</p>
    </div>
  )
}

function SettingsPlaceholder() {
  return (
    <div className="text-center py-20">
      <h2 className="text-2xl font-bold mb-4">Settings</h2>
      <p className="text-muted-foreground">Account settings coming soon.</p>
    </div>
  )
}
