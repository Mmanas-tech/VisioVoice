import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '@/components/layout/Navbar'
import Sidebar from '@/components/layout/Sidebar'
import VideoUploader from '@/components/features/VideoUploader'
import TranscriptionViewer from '@/components/features/TranscriptionViewer'
import AudioPanel from '@/components/features/AudioPanel'
import ProjectsPanel from '@/components/features/ProjectsPanel'
import SettingsPanel from '@/components/features/SettingsPanel'
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
          {activeTab === 'projects' && <ProjectsPanel />}
          {activeTab === 'settings' && <SettingsPanel />}
        </main>
      </div>
    </div>
  )
}
