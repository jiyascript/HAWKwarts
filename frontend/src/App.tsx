import { useState, useEffect, useRef } from 'react'

const FONT = "Georgia, 'Times New Roman', serif"
const MONO = "'JetBrains Mono', monospace"

const C = {
  bg: '#f5f0e8',
  bgDeep: '#ede6d8',
  bgLight: '#f9f5ee',
  red: '#cc0000',
  redDark: '#a30000',
  redDim: 'rgba(204,0,0,0.10)',
  border: 'rgba(0,0,0,0.09)',
  borderRed: 'rgba(204,0,0,0.20)',
  text: '#1a0a0a',
  textDim: '#5a3a3a',
  textFaint: '#9a7a7a',
}

type Page = 'home' | 'about'

interface Message {
  role: 'user' | 'assistant'
  text: string
  ts: string
}

const RESPONSES: Record<string, string> = {
  register: "To register for courses, log in to the student portal and navigate to 'Course Registration' during your assigned enrollment window. Make sure any holds on your account are cleared first — I can check common hold types if you tell me which one you're seeing.",
  courses: "I can help you find courses! What are you looking for — a specific subject, a requirement you need to fulfill, or courses from a particular professor? I can also show you which sections still have open seats.",
  professor: "I can pull up office hours, typical grading style, and which courses they're teaching this semester. Which professor would you like to know about?",
  faq: "Common questions I can answer: add/drop deadlines, transcript requests, degree audit, financial aid holds, prerequisite waivers, and graduation requirements. What do you need?",
  schedule: "I can help you build a schedule! Share your major, year, and any courses you've already completed and I'll map out your remaining requirements with prereqs and coreqs accounted for.",
  hello: "Hi! I'm HawkWarts, your campus academic advisor. I'm here to help with course registration, class schedules, professor info, degree requirements, and any campus FAQs. What can I help you with today?",
  default: "Great question — let me look into that for you. For the most accurate answer, could you tell me your major and year? That helps me tailor my guidance to your specific degree plan.",
}

function pickResponse(input: string): string {
  const l = input.toLowerCase()
  if (l.match(/\b(register|registration|enroll|enrollment|sign up|add|drop)\b/)) return RESPONSES.register
  if (l.match(/\b(course|class|section|subject|credit|syllabus)\b/)) return RESPONSES.courses
  if (l.match(/\b(professor|prof|instructor|teacher|faculty|office hours)\b/)) return RESPONSES.professor
  if (l.match(/\b(faq|help|question|deadline|transcript|hold|aid|graduation|requirement)\b/)) return RESPONSES.faq
  if (l.match(/\b(schedule|flowchart|plan|prerequisite|corequisite|semester)\b/)) return RESPONSES.schedule
  if (l.match(/\b(hello|hi|hey|start|begin|what can)\b/)) return RESPONSES.hello
  return RESPONSES.default
}

function now() { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }

const STARTERS = [
  'How do I register for courses?',
  'Find open sections for Math 100',
  'Tell me about Dr. Jacek',
  'What are the add/drop deadlines?',
]

const FEATURES = [
  { icon: '◈', title: 'Course Registration Help', body: 'Get step-by-step guidance on enrolling in classes, noting prerequisites, resolving inquiries, and navigating course offerings — quick answers for those quick questions.' },
  { icon: '⬡', title: 'Professor Insights', body: "Access office hours, locations, interests, publications and student feedback for any faculty member — so you can make informed decisions before you're locked in." },
  { icon: '◉', title: 'Degree Planning', body: 'HawkWarts can understand your major requirements, track your progress, and flag missing credits or prerequisite gaps before they become problems at registration and even graduation.' },
  { icon: '◆', title: 'Schedule Generation', body: 'Build your very own flowchart with HawkWarts. It will note prerequisites, co-requisites, met requirements, and needed classes straight from your transcript.' },
]

const DEVS = [
  { name: 'Cindy Ambriz' },
  { name: 'Raul Gandara' },
  { name: 'Insuh Hwang' },
  { name: 'Jiafeng Li' },
  { name: 'Clara Reyes' },
  { name: 'Jiya Srathi' },
]

const MOCK_COURSES = [
  { code: 'CS 101', name: 'Intro to Computer Science', status: 'completed', sem: 'Fall 2023' },
  { code: 'MATH 151', name: 'Calculus I', status: 'completed', sem: 'Fall 2023' },
  { code: 'CS 201', name: 'Data Structures', status: 'completed', sem: 'Spring 2024' },
  { code: 'MATH 152', name: 'Calculus II', status: 'completed', sem: 'Spring 2024' },
  { code: 'CS 301', name: 'Algorithms', status: 'in-progress', sem: 'Fall 2024' },
  { code: 'CS 310', name: 'Database Systems', status: 'in-progress', sem: 'Fall 2024' },
  { code: 'CS 401', name: 'Machine Learning', status: 'planned', sem: 'Spring 2025' },
  { code: 'CS 450', name: 'Distributed Systems', status: 'planned', sem: 'Spring 2025' },
]

const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  completed: { bg: 'rgba(16,176,80,0.10)', text: '#0a8c3a', label: 'Completed' },
  'in-progress': { bg: 'rgba(176,120,16,0.10)', text: '#8c6a0c', label: 'In Progress' },
  planned: { bg: C.redDim, text: C.red, label: 'Planned' },
}

// ── shared components ──────────────────────────────────────────────────────────

function Logo({ size = 20, onCream = false }: { size?: number; onCream?: boolean }) {
  const fill = onCream ? C.red : '#fff'
  const bright = onCream ? C.redDark : 'rgba(255,255,255,0.55)'
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2 L4 9 L8 9 L6 19 L12 14 L18 19 L16 9 L20 9 Z" fill={fill} opacity="0.9" />
      <path d="M12 2 L8 9 L12 11.5 L16 9 Z" fill={bright} />
    </svg>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-1 items-center px-4 py-3">
      {[0, 1, 2].map(i => (
        <span key={i} className="typing-dot w-1.5 h-1.5 rounded-full inline-block"
          style={{ backgroundColor: C.red, animationDelay: `${i * 0.2}s` }} />
      ))}
    </div>
  )
}

function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-1" style={{ backgroundColor: C.red }}>
          <Logo size={14} />
        </div>
      )}
      <div style={{ maxWidth: '78%' }}>
        <div className="rounded-2xl px-4 py-3 text-sm leading-relaxed"
          style={isUser
            ? { backgroundColor: C.red, color: '#fff', borderBottomRightRadius: '6px', fontFamily: FONT }
            : { backgroundColor: '#fff', color: C.text, border: `1px solid ${C.border}`, borderBottomLeftRadius: '6px', fontFamily: FONT }}>
          {msg.text}
        </div>
        <div className="mt-1 text-[10px] px-1" style={{ color: C.textFaint, textAlign: isUser ? 'right' : 'left', fontFamily: MONO }}>
          {msg.ts}
        </div>
      </div>
    </div>
  )
}

function useChatState(greeting: string) {
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', text: greeting, ts: now() }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)

  function send(text: string) {
    if (!text.trim()) return
    setMessages(m => [...m, { role: 'user', text: text.trim(), ts: now() }])
    setInput('')
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages(m => [...m, { role: 'assistant', text: pickResponse(text), ts: now() }])
    }, 1200 + Math.random() * 700)
  }

  return { messages, input, setInput, typing, send }
}

function ChatPanel({ greeting, starters, height = '100%' }: { greeting: string; starters?: string[]; height?: string }) {
  const { messages, input, setInput, typing, send } = useChatState(greeting)
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, typing])

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  return (
    <div className="flex flex-col overflow-hidden"
      style={{ border: `1px solid ${C.border}`, backgroundColor: '#fff', height, boxShadow: '0 4px 32px rgba(0,0,0,0.08)', borderRadius: '16px' }}>
      <div className="flex items-center gap-3 px-5 py-3.5" style={{ borderBottom: `1px solid ${C.border}`, backgroundColor: C.red, borderRadius: '16px 16px 0 0' }}>
        <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.25)' }}>
          <Logo size={16} />
        </div>
        <div>
          <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: '14px', color: '#fff' }}>HawkWarts Advisor</div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 inline-block" />
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)', fontFamily: MONO }}>Online · Academic Advisor</span>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4" style={{ backgroundColor: C.bgLight }}>
        {messages.map((m, i) => <ChatBubble key={i} msg={m} />)}
        {typing && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center" style={{ backgroundColor: C.red }}><Logo size={14} /></div>
            <div style={{ backgroundColor: '#fff', border: `1px solid ${C.border}`, borderRadius: '16px', borderBottomLeftRadius: '6px' }}><TypingIndicator /></div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {starters && messages.length <= 1 && (
        <div className="px-5 pb-3 flex flex-wrap gap-2" style={{ backgroundColor: C.bgLight }}>
          {starters.map(p => (
            <button key={p} onClick={() => send(p)}
              className="text-xs px-3 py-1.5 rounded-full transition-all duration-150"
              style={{ border: `1px solid ${C.borderRed}`, color: C.textDim, backgroundColor: 'transparent', fontFamily: MONO }}
              onMouseEnter={e => { e.currentTarget.style.backgroundColor = C.redDim; e.currentTarget.style.color = C.red }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = C.textDim }}>
              {p}
            </button>
          ))}
        </div>
      )}
      <div className="px-4 py-3 flex items-end gap-3" style={{ borderTop: `1px solid ${C.border}`, backgroundColor: '#fff', borderRadius: '0 0 16px 16px' }}>
        <textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKey}
          placeholder="Ask about registration, courses, professors…" rows={1}
          className="flex-1 resize-none text-sm leading-relaxed outline-none bg-transparent"
          style={{ color: C.text, fontFamily: FONT, maxHeight: '96px' }} />
        <button onClick={() => send(input)} disabled={!input.trim() || typing}
          className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150"
          style={{ backgroundColor: input.trim() && !typing ? C.red : C.border, cursor: input.trim() && !typing ? 'pointer' : 'not-allowed' }}
          onMouseEnter={e => { if (input.trim() && !typing) e.currentTarget.style.backgroundColor = C.redDark }}
          onMouseLeave={e => { e.currentTarget.style.backgroundColor = input.trim() && !typing ? C.red : C.border }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M2 8h12M10 4l4 4-4 4" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  )
}

// ── pages ──────────────────────────────────────────────────────────────────────

function HomePage() {
  return (
    // Full-viewport split: left = schedule, right = chat
    <div className="flex flex-col lg:flex-row" style={{ minHeight: '100vh', paddingTop: '56px' }}>

      {/* Left half — Schedule */}
      <div className="flex-1 flex flex-col px-8 py-10 overflow-auto"
        style={{ backgroundColor: C.bgDeep, borderRight: `1px solid ${C.border}` }}>
        <div className="mb-6">
          <span style={{ fontFamily: MONO, fontSize: '11px', color: C.textFaint, letterSpacing: '0.14em' }}>SCHEDULE GENERATION</span>
          <h2 className="mt-2" style={{ fontFamily: FONT, fontSize: 'clamp(1.5rem, 2.5vw, 2rem)', fontWeight: 700, letterSpacing: '-0.01em', color: C.text, lineHeight: 1.15 }}>
            Your degree roadmap.
          </h2>
          <p className="mt-2" style={{ color: C.textDim, fontSize: '14px', lineHeight: 1.7, fontFamily: FONT }}>
            HawkWarts maps your completed courses, flags prerequisites, and plans your remaining semesters from your transcript.
          </p>
        </div>

        <div className="rounded-xl overflow-hidden flex flex-col flex-1" style={{ border: `1px solid ${C.border}`, backgroundColor: '#fff' }}>
          <div className="px-5 py-3 flex items-center justify-between flex-wrap gap-2"
            style={{ borderBottom: `1px solid ${C.border}`, backgroundColor: C.bg }}>
            <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: '13px', color: C.text }}>CS — Computer Science B.S.</span>
            <div className="flex gap-4 text-[10px]" style={{ fontFamily: MONO }}>
              {Object.entries(STATUS_COLORS).map(([k, v]) => (
                <span key={k} className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ backgroundColor: v.text }} />
                  <span style={{ color: C.textFaint }}>{v.label}</span>
                </span>
              ))}
            </div>
          </div>
          <div className="overflow-auto flex-1">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['Code', 'Course Name', 'Semester', 'Status'].map(h => (
                    <th key={h} className="text-left px-5 py-3" style={{ fontSize: '10px', color: C.textFaint, fontFamily: MONO, letterSpacing: '0.08em', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MOCK_COURSES.map((c, i) => {
                  const sc = STATUS_COLORS[c.status]
                  return (
                    <tr key={i} style={{ borderBottom: i < MOCK_COURSES.length - 1 ? `1px solid ${C.border}` : 'none' }}
                      className="transition-colors duration-150"
                      onMouseEnter={e => (e.currentTarget.style.backgroundColor = C.bgLight)}
                      onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
                      <td className="px-5 py-3" style={{ fontFamily: MONO, color: C.red, fontWeight: 500 }}>{c.code}</td>
                      <td className="px-5 py-3" style={{ color: C.text, fontFamily: FONT }}>{c.name}</td>
                      <td className="px-5 py-3" style={{ color: C.textDim, fontFamily: MONO }}>{c.sem}</td>
                      <td className="px-5 py-3">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium"
                          style={{ backgroundColor: sc.bg, color: sc.text, fontFamily: MONO }}>{sc.label}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="px-5 py-3" style={{ borderTop: `1px solid ${C.border}`, backgroundColor: C.bg }}>
            <span style={{ fontSize: '11px', color: C.textFaint, fontFamily: MONO }}>8 courses · 24 credits remaining</span>
          </div>
        </div>
      </div>

      {/* Right half — HawkWarts AI chat */}
      <div className="flex-1 flex flex-col px-8 py-10" style={{ backgroundColor: C.bg }}>
        <div className="mb-6">
          <span style={{ fontFamily: MONO, fontSize: '11px', color: C.textFaint, letterSpacing: '0.14em' }}>HAWKWARTS AI</span>
          <h2 className="mt-2" style={{ fontFamily: FONT, fontSize: 'clamp(1.5rem, 2.5vw, 2rem)', fontWeight: 700, letterSpacing: '-0.01em', color: C.text, lineHeight: 1.15 }}>
            Your campus advisor,<br /><span style={{ color: C.red }}>always ready.</span>
          </h2>
          <p className="mt-2" style={{ color: C.textDim, fontSize: '14px', lineHeight: 1.7, fontFamily: FONT }}>
            Ask about registration, courses, professors, degree requirements, or any campus FAQ — available 24/7.
          </p>
        </div>
        <div className="flex-1" style={{ minHeight: '460px' }}>
          <ChatPanel
            greeting="Hi! I'm HawkWarts, your campus academic advisor. Ask me about course registration, professors, class schedules, degree requirements, or any campus FAQ."
            starters={STARTERS}
            height="100%"
          />
        </div>
      </div>
    </div>
  )
}

function AboutPage() {
  return (
    <div style={{ backgroundColor: C.bg, minHeight: '100vh', paddingTop: '56px' }}>

      {/* About HawkWarts — first */}
      <section className="py-20" style={{ borderBottom: `1px solid ${C.border}` }}>
        <div className="max-w-4xl mx-auto px-6">
          <span style={{ fontFamily: MONO, fontSize: '11px', color: C.textFaint, letterSpacing: '0.14em' }}>ABOUT HAWKWARTS</span>
          <h1 className="mt-4 mb-5" style={{ fontFamily: FONT, fontSize: 'clamp(2rem, 4vw, 3rem)', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.1, color: C.text }}>
            Built for students,<br /><span style={{ color: C.red }}>by students.</span>
          </h1>
          <p style={{ fontSize: '16px', color: C.textDim, lineHeight: 1.7, maxWidth: '560px', fontFamily: FONT }}>
            HawkWarts is a trustworthy, reliable agentic AI built to assist with the questions that matter most to campus life — registration, courses, professors, and everyday FAQs. No runaround, no guesswork.
          </p>
        </div>
      </section>

      {/* What HawkWarts Handles — second */}
      <section className="py-20" style={{ backgroundColor: C.bgDeep, borderBottom: `1px solid ${C.border}` }}>
        <div className="max-w-4xl mx-auto px-6">
          <span style={{ fontFamily: MONO, fontSize: '11px', color: C.textFaint, letterSpacing: '0.14em' }}>WHAT HAWKWARTS HANDLES</span>
          <h2 className="mt-3 mb-12" style={{ fontFamily: FONT, fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 700, letterSpacing: '-0.01em', lineHeight: 1.1, color: C.text }}>
            Every question students actually ask.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px"
            style={{ border: `1px solid ${C.border}`, backgroundColor: C.border }}>
            {FEATURES.map(f => (
              <div key={f.title} className="p-7 transition-colors duration-200 cursor-default"
                style={{ backgroundColor: C.bg }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = C.bgDeep)}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = C.bg)}>
                <div style={{ fontSize: '22px', color: C.red, marginBottom: '14px', fontFamily: 'monospace' }}>{f.icon}</div>
                <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: '15px', marginBottom: '8px', color: C.text }}>{f.title}</div>
                <p style={{ fontSize: '13px', color: C.textDim, lineHeight: 1.7, fontFamily: FONT }}>{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Developers */}
      <section className="py-20" style={{ backgroundColor: C.bg }}>
        <div className="max-w-4xl mx-auto px-6">
          <span style={{ fontFamily: MONO, fontSize: '11px', color: C.textFaint, letterSpacing: '0.14em' }}>THE TEAM</span>
          <h2 className="mt-3 mb-10" style={{ fontFamily: FONT, fontSize: 'clamp(1.6rem, 2.5vw, 2.2rem)', fontWeight: 700, letterSpacing: '-0.01em', color: C.text }}>
            Meet the developers.
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
            {DEVS.map(d => (
              <div key={d.name} className="rounded-xl p-6 transition-colors duration-200"
                style={{ backgroundColor: C.bgDeep, border: `1px solid ${C.border}` }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = C.borderRed; e.currentTarget.style.backgroundColor = '#fff' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.backgroundColor = C.bgDeep }}>
                <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
                  style={{ backgroundColor: C.redDim, border: `1px solid ${C.borderRed}` }}>
                  <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: '15px', color: C.red }}>
                    {d.name.split(' ').map(n => n[0]).join('')}
                  </span>
                </div>
                <div style={{ fontFamily: FONT, fontWeight: 700, fontSize: '15px', color: C.text, marginBottom: '14px' }}>{d.name}</div>
                <div className="flex flex-col gap-2.5">
                  <a href="#" className="flex items-center gap-2 text-xs transition-colors duration-150"
                    style={{ color: C.textFaint, textDecoration: 'none', fontFamily: MONO }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#0a66c2')}
                    onMouseLeave={e => (e.currentTarget.style.color = C.textFaint)}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z" />
                      <circle cx="4" cy="4" r="2" />
                    </svg>
                    LinkedIn
                  </a>
                  <a href="#" className="flex items-center gap-2 text-xs transition-colors duration-150"
                    style={{ color: C.textFaint, textDecoration: 'none', fontFamily: MONO }}
                    onMouseEnter={e => (e.currentTarget.style.color = C.text)}
                    onMouseLeave={e => (e.currentTarget.style.color = C.textFaint)}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                    </svg>
                    GitHub
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

// ── root ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'smooth' }) }, [page])

  return (
    <div style={{ minHeight: '100vh', backgroundColor: C.bg, color: C.text, fontFamily: FONT }}>

      <nav className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          borderBottom: `1px solid ${C.border}`,
          backgroundColor: 'rgba(245,240,232,0.96)',
          backdropFilter: 'blur(16px)',
        }}>
        <div className="max-w-none px-8 h-14 flex items-center justify-between">
          <button className="flex items-center gap-2.5" onClick={() => setPage('home')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
            <Logo size={22} onCream />
            <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: '16px', letterSpacing: '0.02em', color: C.text }}>HAWKWARTS</span>
          </button>
          <div className="flex items-center gap-7">
            {(['home', 'about'] as Page[]).map(id => (
              <button key={id} onClick={() => setPage(id)}
                className="text-sm transition-colors duration-200"
                style={{ color: page === id ? C.red : C.textFaint, background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontWeight: page === id ? 700 : 400, fontFamily: FONT }}
                onMouseEnter={e => (e.currentTarget.style.color = C.red)}
                onMouseLeave={e => (e.currentTarget.style.color = page === id ? C.red : C.textFaint)}>
                {id === 'home' ? 'Home' : 'About'}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {page === 'home' && <HomePage />}
      {page === 'about' && <AboutPage />}

      <footer style={{ borderTop: `1px solid ${C.border}`, backgroundColor: C.bgDeep }}>
        <div className="max-w-none px-8 py-7 flex items-center justify-center">
          <button className="flex items-center gap-2" onClick={() => setPage('home')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
            <Logo size={16} onCream />
            <span style={{ fontFamily: FONT, fontWeight: 700, fontSize: '13px', color: C.text }}>HAWKWARTS</span>
          </button>
        </div>
      </footer>
    </div>
  )
}
