import React from 'react'
import { cn } from '@/utils/cn'
import { Upload, FileText, FolderOpen, Settings, Mic } from 'lucide-react'

const tabs = [
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'transcriptions', label: 'Transcriptions', icon: FileText },
  { id: 'projects', label: 'Projects', icon: FolderOpen },
  { id: 'audio', label: 'Audio', icon: Mic },
  { id: 'settings', label: 'Settings', icon: Settings },
]

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="hidden md:flex flex-col w-64 min-h-[calc(100vh-64px)] border-r border-border bg-secondary/30">
      <div className="p-4 space-y-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors',
              activeTab === tab.id
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            )}
          >
            <tab.icon size={18} />
            {tab.label}
          </button>
        ))}
      </div>
    </aside>
  )
}
