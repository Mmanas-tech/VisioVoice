import React from 'react'
import Navbar from '@/components/layout/Navbar'
import { Button } from '@/components/ui/Button'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Brain, Mic, Shield, Zap } from 'lucide-react'

const features = [
  { icon: Brain, title: 'AI-Powered', desc: 'State-of-the-art deep learning models for accurate lip reading' },
  { icon: Mic, title: 'Voice Synthesis', desc: 'Generate natural speech from silent video transcriptions' },
  { icon: Shield, title: 'Secure', desc: 'End-to-end encryption for all video data and transcriptions' },
  { icon: Zap, title: 'Real-time', desc: 'Fast processing with live progress updates' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[128px]" />

        <div className="relative z-10 text-center px-6 max-w-4xl mx-auto pt-20">
          <h1 className="text-[clamp(3rem,8vw,6rem)] font-bold leading-[1.05] tracking-[-0.05em] mb-6 animate-fade-up">
            Lip-Reading <span className="text-primary">AI</span>
          </h1>

          <p className="text-foreground/80 text-[clamp(1.125rem,2.5vw,1.875rem)] font-light mb-4 animate-fade-up" style={{ animationDelay: '0.2s' }}>
            Transcribe speech from silent video.
          </p>

          <p className="text-muted-foreground text-[clamp(0.875rem,1.5vw,1.125rem)] font-light mb-8 max-w-2xl mx-auto animate-fade-up" style={{ animationDelay: '0.35s' }}>
            Advanced AI converts silent video footage into accurate transcriptions. Perfect for accessibility, security monitoring, and content creation.
          </p>

          <div className="flex flex-wrap justify-center gap-4 animate-fade-up" style={{ animationDelay: '0.5s' }}>
            <Button size="lg" onClick={() => navigate('/dashboard')}>
              Try Now <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
            <Button size="lg" variant="outline" onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}>
              Learn More
            </Button>
          </div>

          <p className="text-muted-foreground/60 text-xs mt-8 animate-fade-up" style={{ animationDelay: '0.65s' }}>
            Trusted by security teams worldwide. Multi-language support. Real-time processing.
          </p>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-16">
            Powerful <span className="text-primary">Features</span>
          </h2>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, i) => (
              <div
                key={feature.title}
                className="p-6 rounded-lg border border-border bg-secondary/30 hover:border-primary/50 transition-all duration-300"
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                <feature.icon className="w-10 h-10 text-primary mb-4" />
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 border-t border-border">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">
            Ready to get <span className="text-primary">started</span>?
          </h2>
          <p className="text-muted-foreground mb-8">
            Upload your first video and see the power of AI lip reading.
          </p>
          <Button size="lg" onClick={() => navigate('/dashboard')}>
            Start Transcribing <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-24 px-6 border-t border-border">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-16">
            How It <span className="text-primary">Works</span>
          </h2>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: '01', title: 'Upload Video', desc: 'Upload any silent video of a person speaking. We support MP4, MOV, AVI, and MKV formats up to 2GB.' },
              { step: '02', title: 'AI Analysis', desc: 'Our deep learning model analyzes mouth movements frame-by-frame, using 3D convolutional neural networks and attention mechanisms.' },
              { step: '03', title: 'Get Results', desc: 'Receive accurate transcriptions with timestamps, confidence scores, and optional audio synthesis.' },
            ].map((item, i) => (
              <div key={item.step} className="text-center">
                <div className="text-5xl font-bold text-primary/20 mb-4">{item.step}</div>
                <h3 className="text-xl font-semibold mb-2">{item.title}</h3>
                <p className="text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-muted-foreground">
            LipRead AI. All rights reserved.
          </p>
          <div className="flex gap-6">
            <a href="#features" className="text-sm text-muted-foreground hover:text-foreground">Features</a>
            <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground">How It Works</a>
            <a href="mailto:support@lipread.ai" className="text-sm text-muted-foreground hover:text-foreground">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
