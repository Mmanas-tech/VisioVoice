import React from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import Navbar from '@/components/layout/Navbar'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="flex flex-col items-center justify-center min-h-screen px-4">
        <h1 className="text-7xl font-bold text-primary mb-4">404</h1>
        <p className="text-xl text-muted-foreground mb-8">Page not found</p>
        <Link to="/">
          <Button>Go Home</Button>
        </Link>
      </div>
    </div>
  )
}
