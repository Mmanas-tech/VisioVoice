import React from 'react'
import { cn } from '@/utils/cn'

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'w-4 h-4 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-3',
}

function Spinner({ size = 'md', className, ...props }: SpinnerProps) {
  return (
    <div
      className={cn('animate-spin rounded-full border-primary border-t-transparent', sizeClasses[size], className)}
      {...props}
    />
  )
}

function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Spinner size="lg" />
      <p className="text-sm text-muted-foreground">{text}</p>
    </div>
  )
}

export { Spinner, LoadingSpinner }
