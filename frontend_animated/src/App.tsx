import { useState, useRef, CSSProperties, useEffect, useLayoutEffect } from 'react';

const MASCOT_SRCS = {
  hat:       '/assets/hat-bf0c14.png',
  transform: '/assets/hat-to-bird-fast.gif',
  reverse:   '/assets/bird-to-hat-fast.gif',
  flight:    '/assets/bird-flight.gif',
} as const;
type MascotAsset = keyof typeof MASCOT_SRCS;

type Phase = 'landing' | 'to-chat' | 'chat' | 'to-landing';
type Layout = 'chat' | 'planner';

// Message types
interface CourseCard {
  code: string; name: string; credits: number;
  description: string; tags: string[]; prereqs: string;
}
interface Message {
  from: 'hawkwarts' | 'student';
  text: string;
  cards?: CourseCard[];
}

// Plan types
type CourseStatus = 'completed' | 'planned';
interface PlanCourse {
  code: string; name: string; credits: number;
  status: CourseStatus; suggested?: boolean;
}
interface PlanSemester {
  id: string; label: string; sublabel: string;
  courses: PlanCourse[]; upcoming?: boolean;
}
interface ArrowDatum {
  x1: number; y1: number; x2: number; y2: number;
  type: 'prereq' | 'coreq';
}

const SUGGESTED_PROMPTS = ['Find courses', 'Plan my semester', 'Ask about registration'];

const PLANNER_MESSAGES: Message[] = [
  { from: 'student', text: "I only have two semesters left. Can you help me finish my AI requirements?" },
  { from: 'hawkwarts', text: "Absolutely. I mapped your completed coursework and created a two-semester plan based on your remaining AI requirements. You can see the full prerequisite chain and your recommended path in the Schedule Builder." },
];

// Columns arranged so the primary AI chain (col 2) runs straight down:
// CS 115 → CS 116 → CS 331 → CS 480 → CS 584 → CS 583
const PLAN_SEMESTERS: PlanSemester[] = [
  {
    id: 's1', label: 'Fall 2022', sublabel: 'Completed',
    courses: [
      { code: 'CS 100',  name: 'Intro to the Profession',        credits: 1, status: 'completed' },
      { code: 'MATH 151',name: 'Calculus I',                      credits: 5, status: 'completed' },
      { code: 'CS 115',  name: 'Object-Oriented Programming I',   credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's2', label: 'Spring 2023', sublabel: 'Completed',
    courses: [
      { code: 'CS 330',  name: 'Discrete Structures',             credits: 3, status: 'completed' },
      { code: 'MATH 152',name: 'Calculus II',                     credits: 4, status: 'completed' },
      { code: 'CS 116',  name: 'Object-Oriented Programming II',  credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's3', label: 'Fall 2023', sublabel: 'Completed',
    courses: [
      { code: 'CS 350',  name: 'Computer Organization',           credits: 3, status: 'completed' },
      { code: 'MATH 474',name: 'Probability & Statistics',        credits: 3, status: 'completed' },
      { code: 'CS 331',  name: 'Data Structures & Algorithms',    credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's4', label: 'Spring 2024', sublabel: 'Completed',
    courses: [
      { code: 'CS 430',  name: 'Introduction to Algorithms',      credits: 3, status: 'completed' },
      { code: 'CS 440',  name: 'Programming Languages',           credits: 3, status: 'completed' },
      { code: 'CS 480',  name: 'Artificial Intelligence',         credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's5', label: 'Fall 2024', sublabel: 'Completed',
    courses: [
      { code: 'CS 481',  name: 'AI Language Understanding',       credits: 3, status: 'completed' },
      { code: 'CS 422',  name: 'Data Mining',                     credits: 3, status: 'completed' },
      { code: 'CS 425',  name: 'Database Organization',           credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's6', label: 'Spring 2025', sublabel: 'Completed',
    courses: [
      { code: 'CS 485',  name: 'Computers & Society',             credits: 3, status: 'completed' },
      { code: 'FREE',    name: 'Free Elective',                   credits: 3, status: 'completed' },
      { code: 'CS 584',  name: 'Machine Learning',                credits: 3, status: 'completed' },
    ],
  },
  {
    id: 's7', label: 'Fall 2026', sublabel: 'Planned', upcoming: true,
    courses: [
      { code: 'TECH-EL', name: 'Technical Elective',              credits: 3, status: 'planned' },
      { code: 'CS 577',  name: 'Adv. Deep Learning Topics',       credits: 3, status: 'planned', suggested: true },
      { code: 'CS 583',  name: 'Deep Learning',                   credits: 3, status: 'planned', suggested: true },
    ],
  },
  {
    id: 's8', label: 'Spring 2027', sublabel: 'Planned', upcoming: true,
    courses: [
      { code: 'IPRO',    name: 'IPRO / Degree Requirement',       credits: 3, status: 'planned' },
      { code: 'TECH-EL-2', name: 'Technical Elective',            credits: 3, status: 'planned' },
      { code: 'AI-EL',   name: 'AI Elective',                     credits: 3, status: 'planned' },
    ],
  },
];

// Prerequisite connections — col positions designed to minimise crossings.
// Primary AI chain (col 2) is all-straight: CS115→CS116→CS331→CS480→CS584→CS583→AI-EL
const PLAN_CONNECTIONS: [string, string, 'prereq' | 'coreq'][] = [
  ['CS 115',  'CS 116',  'prereq'],
  ['MATH 151','MATH 152','prereq'],
  ['CS 116',  'CS 331',  'prereq'],
  ['CS 330',  'CS 331',  'prereq'],
  ['MATH 152','MATH 474','prereq'],
  ['CS 331',  'CS 430',  'prereq'],
  ['CS 331',  'CS 480',  'prereq'],
  ['CS 480',  'CS 481',  'prereq'],
  ['CS 480',  'CS 584',  'prereq'],
  ['CS 584',  'CS 583',  'prereq'],
  ['CS 584',  'CS 577',  'prereq'],
  ['CS 583',  'AI-EL',   'prereq'],
];

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

function afterNextPaint(): Promise<void> {
  return new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

function Disclaimer() {
  return (
    <div className="disclaimer">
      <div className="disclaimer-inner">
        <svg className="disclaimer-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p className="disclaimer-text">
          <strong>Always verify important information.</strong> AI can make
          mistakes or produce inaccurate information. We recommend confirming
          final decisions about courses, registration, degree requirements, and
          other academic matters with your{' '}
          <strong>academic advisor</strong> or the appropriate{' '}
          <strong>university office</strong>.
        </p>
      </div>
    </div>
  );
}

// ── Schedule Builder ────────────────────────────────────────────

function ScheduleBuilder() {
  const blockRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const contentRef = useRef<HTMLDivElement>(null);
  const [arrows, setArrows] = useState<ArrowDatum[]>([]);

  const reg = (code: string) => (el: HTMLDivElement | null) => {
    if (el) blockRefs.current.set(code, el);
    else blockRefs.current.delete(code);
  };

  useLayoutEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    const base = content.getBoundingClientRect();
    const computed: ArrowDatum[] = [];
    for (const [from, to, type] of PLAN_CONNECTIONS) {
      const a = blockRefs.current.get(from);
      const b = blockRefs.current.get(to);
      if (!a || !b) continue;
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      computed.push({
        x1: ar.left - base.left + ar.width / 2,
        y1: ar.bottom - base.top,
        x2: br.left - base.left + br.width / 2,
        y2: br.top - base.top,
        type,
      });
    }
    setArrows(computed);
  }, []);

  function pathD(a: ArrowDatum): string {
    if (Math.abs(a.x2 - a.x1) < 4) {
      return `M ${a.x1} ${a.y1} L ${a.x2} ${a.y2}`;
    }
    const cy = (a.y1 + a.y2) / 2;
    return `M ${a.x1} ${a.y1} C ${a.x1} ${cy} ${a.x2} ${cy} ${a.x2} ${a.y2}`;
  }

  const completedSems = PLAN_SEMESTERS.filter(s => !s.upcoming);
  const plannedSems   = PLAN_SEMESTERS.filter(s =>  s.upcoming);

  return (
    <div className="builder">
      <div className="builder-header">
        <div className="builder-head-left">
          <h2 className="builder-title">Schedule Builder</h2>
          <p className="builder-subtitle">Build and visualize your academic plan.</p>
        </div>
        <div className="builder-head-right">
          <span className="builder-meta">CS &mdash; AI Track</span>
          <span className="builder-meta-sep">·</span>
          <span className="builder-meta builder-meta-rem">2 semesters remaining</span>
        </div>
      </div>

      <div className="builder-scroll">
        <div className="builder-content" ref={contentRef}>

          {/* SVG prerequisite arrow overlay */}
          <svg className="builder-svg" aria-hidden="true">
            <defs>
              <marker id="mh-pre" markerWidth="7" markerHeight="7"
                refX="6" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">
                <path d="M 1,1 L 6,3.5 L 1,6" fill="none"
                  stroke="#c2b5ab" strokeWidth="1.1"
                  strokeLinejoin="round" strokeLinecap="round" />
              </marker>
              <marker id="mh-co" markerWidth="7" markerHeight="7"
                refX="6" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">
                <path d="M 1,1 L 6,3.5 L 1,6" fill="none"
                  stroke="#c2b5ab" strokeWidth="1.1"
                  strokeLinejoin="round" strokeLinecap="round" />
              </marker>
            </defs>
            {arrows.map((a, i) => (
              <path
                key={i}
                d={pathD(a)}
                fill="none"
                stroke="#ccc2b8"
                strokeWidth="1.25"
                strokeDasharray={a.type === 'coreq' ? '4.5 2.5' : undefined}
                markerEnd={`url(#mh-${a.type === 'prereq' ? 'pre' : 'co'})`}
              />
            ))}
          </svg>

          {/* Previous coursework */}
          <div className="plan-section-divider">
            <span className="plan-section-label">Previous Coursework</span>
          </div>

          {completedSems.map(sem => (
            <div key={sem.id} className="sem-row">
              <div className="sem-label-col">
                <span className="sem-name">{sem.label}</span>
                <span className="sem-badge sem-badge-done">Completed</span>
              </div>
              <div className="sem-track">
                {sem.courses.map(c => (
                  <div key={c.code} ref={reg(c.code)} className="cb cb-done">
                    <div className="cb-head">
                      <span className="cb-code">{c.code}</span>
                      <span className="cb-check" aria-label="Completed">✓</span>
                    </div>
                    <span className="cb-name">{c.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Upcoming plan */}
          <div className="plan-section-divider plan-section-divider-upcoming">
            <span className="plan-section-label">Remaining &mdash; 2 Semesters</span>
          </div>

          {plannedSems.map(sem => (
            <div key={sem.id} className="sem-row sem-row-upcoming">
              <div className="sem-label-col">
                <span className="sem-name sem-name-upcoming">{sem.label}</span>
                <span className="sem-badge sem-badge-plan">Planned</span>
              </div>
              <div className="sem-track">
                {sem.courses.map(c => (
                  <div key={c.code} ref={reg(c.code)}
                    className={`cb cb-plan${c.suggested ? ' cb-suggested' : ''}`}>
                    <div className="cb-head">
                      <span className="cb-code cb-code-plan">{c.code}</span>
                      {c.suggested
                        ? <span className="cb-hw-badge" title="Recommended by HAWKwarts">★</span>
                        : <span className="cb-plan-dot" />
                      }
                    </div>
                    <span className="cb-name cb-name-plan">{c.name}</span>
                    <span className="cb-credits">{c.credits} cr</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

        </div>
      </div>

      <div className="builder-legend">
        <div className="legend-item">
          <svg width="34" height="10" viewBox="0 0 34 10" aria-hidden="true">
            <line x1="1" y1="5" x2="27" y2="5" stroke="#76777B" strokeWidth="1.3" />
            <path d="M 24,2.5 L 30,5 L 24,7.5" stroke="#76777B" strokeWidth="1.3"
              fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Prerequisite</span>
        </div>
        <div className="legend-item">
          <svg width="34" height="10" viewBox="0 0 34 10" aria-hidden="true">
            <line x1="1" y1="5" x2="27" y2="5" stroke="#76777B" strokeWidth="1.3" strokeDasharray="4 2.5" />
            <path d="M 24,2.5 L 30,5 L 24,7.5" stroke="#76777B" strokeWidth="1.3"
              fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Corequisite</span>
        </div>
        <div className="legend-sep" />
        <div className="legend-item">
          <span className="legend-chip legend-chip-done">✓</span>
          <span>Completed</span>
        </div>
        <div className="legend-item">
          <span className="legend-chip legend-chip-plan">—</span>
          <span>Planned</span>
        </div>
        <div className="legend-item">
          <span className="legend-chip legend-chip-hw">★</span>
          <span>HAWKwarts suggestion</span>
        </div>
      </div>
    </div>
  );
}

// ── App ─────────────────────────────────────────────────────────

export default function App() {
  const [phase, setPhase] = useState<Phase>('landing');
  const [layout, setLayout] = useState<Layout>('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [landingHatHidden, setLandingHatHidden] = useState(false);
  const [chatHawkHidden, setChatHawkHidden] = useState(false);
  const [flyStyle, setFlyStyle] = useState<CSSProperties | null>(null);
  const [flyAsset, setFlyAsset] = useState<MascotAsset>('flight');
  const [chatVisible, setChatVisible] = useState(false);

  const landingHatRef = useRef<HTMLDivElement>(null);
  const chatHawkRef   = useRef<HTMLImageElement>(null);

  const inTransition = phase === 'to-chat' || phase === 'to-landing';
  const PLANNING_RE = /plan|semester|schedule|degree|pathway|curriculum|sequence/i;

  useEffect(() => {
    Object.values(MASCOT_SRCS).forEach(src => {
      const image = new Image();
      image.src = src;
    });
  }, []);

  async function goToChat() {
    if (inTransition || phase === 'chat') return;
    const src = landingHatRef.current!.getBoundingClientRect();
    setFlyAsset('transform');
    setFlyStyle({ left: `${src.left}px`, top: `${src.top}px`, width: `${src.width}px`, height: `${src.height}px` });
    setChatHawkHidden(true);
    setPhase('to-chat');
    const transformationDone = sleep(1040);

    // Keep the static hat in place until the first GIF frame has painted over it.
    await afterNextPaint();
    setLandingHatHidden(true);

    // Hold the landing page until the transformation reaches its final frame.
    await transformationDone;

    // Begin the page crossfade as the completed transformation starts flying.
    setChatVisible(true);
    setFlyAsset('flight');
    await sleep(30);
    const dst = chatHawkRef.current!.getBoundingClientRect();
    setFlyStyle({
      left: `${dst.left}px`, top: `${dst.top}px`, width: `${dst.width}px`, height: `${dst.height}px`,
      transition: ['left 0.72s cubic-bezier(0.4,0,0.2,1)', 'top 0.72s cubic-bezier(0.4,0,0.2,1)',
        'width 0.72s cubic-bezier(0.4,0,0.2,1)', 'height 0.72s cubic-bezier(0.4,0,0.2,1)'].join(', '),
    });
    await sleep(750);
    setFlyStyle({ left: `${dst.left}px`, top: `${dst.top + 9}px`, width: `${dst.width}px`, height: `${dst.height}px`, transition: 'top 0.11s ease-in' });
    await sleep(110);
    setFlyStyle({ left: `${dst.left}px`, top: `${dst.top}px`, width: `${dst.width}px`, height: `${dst.height}px`, transition: 'top 0.14s ease-out' });
    await sleep(140);
    setChatHawkHidden(false);
    setFlyStyle(null);
    setPhase('chat');
  }

  async function goToLanding() {
    if (inTransition || phase === 'landing') return;
    const src = chatHawkRef.current!.getBoundingClientRect();
    setFlyAsset('flight');
    setFlyStyle({ left: `${src.left}px`, top: `${src.top}px`, width: `${src.width}px`, height: `${src.height}px` });
    setChatHawkHidden(true);
    setPhase('to-landing');
    await sleep(30);
    const dst = landingHatRef.current!.getBoundingClientRect();
    setLandingHatHidden(true);
    setFlyStyle({
      left: `${dst.left}px`, top: `${dst.top}px`, width: `${dst.width}px`, height: `${dst.height}px`,
      transition: ['left 0.65s cubic-bezier(0.4,0,0.2,1)', 'top 0.65s cubic-bezier(0.4,0,0.2,1)',
        'width 0.65s cubic-bezier(0.4,0,0.2,1)', 'height 0.65s cubic-bezier(0.4,0,0.2,1)'].join(', '),
    });
    await sleep(200);
    setChatVisible(false);
    await sleep(480);

    // Transform the returned bird back into the hat at the landing position.
    setFlyAsset('reverse');
    await sleep(1040);

    setLandingHatHidden(false);
    setFlyStyle(null);
    setPhase('landing');
    setLayout('chat');
  }

  function sendMessage(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text) return;
    setMessages(prev => [...prev, { from: 'student', text }]);
    setInput('');
    if (PLANNING_RE.test(text)) {
      setLayout('planner');
      setMessages(PLANNER_MESSAGES);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  const landingOpacity = (
    phase === 'landing' ||
    phase === 'to-landing' ||
    (phase === 'to-chat' && !chatVisible)
  ) ? 1 : 0;
  const chatOpacity    = chatVisible || phase === 'chat' ? 1 : 0;

  return (
    <div className="app-shell">

      {flyStyle && (
        <img src={MASCOT_SRCS[flyAsset]} alt="" aria-hidden="true" className="flying-hat" style={flyStyle} />
      )}

      {/* Landing screen */}
      <div className="page-root" style={{
        opacity: landingOpacity,
        transition: inTransition ? 'opacity 0.45s ease' : 'none',
        pointerEvents: phase === 'landing' ? 'auto' : 'none',
      }}>
        <main className="hero">
          <div className="hero-inner">
            <button className="logo-btn" aria-label="Enter HAWKwarts" onClick={goToChat} disabled={inTransition}>
              <div ref={landingHatRef} className="logo-img-stack" style={{ opacity: landingHatHidden ? 0 : 1 }}>
                <img src={MASCOT_SRCS.hat} alt="HAWKwarts wizard hat logo" className="logo-mascot-layer" />
              </div>
              <span className="logo-hint">Click to start</span>
            </button>
            <div className="hero-text">
              <h1 className="title">HAWKwarts</h1>
              <p className="description">
                Your AI guide to campus life — helping with registration, courses,
                professors, and everyday questions. Reliable answers, without the run
                <svg className="runaround-svg" viewBox="0 0 92 32"
                  xmlns="http://www.w3.org/2000/svg" role="img" aria-label="around"
                  style={{ overflow: 'visible' }}>
                  <defs><path id="runaround-arc" d="M 3,5 Q 46,25 89,5" /></defs>
                  <text fontFamily="Georgia, serif" fontSize="16" fill="#1a1a1a">
                    <textPath href="#runaround-arc" startOffset="50%" textAnchor="middle">
                      a r o u n d .
                    </textPath>
                  </text>
                </svg>
              </p>
            </div>
          </div>
        </main>
        <Disclaimer />
      </div>

      {/* Chat screen */}
      <div className="page-root chat-screen-overlay" style={{
        opacity: chatOpacity,
        transition: inTransition ? 'opacity 0.45s ease' : 'none',
        pointerEvents: phase === 'chat' ? 'auto' : 'none',
      }}>
        <header className="chat-header">
          <span className="chat-header-title">Illinois Tech</span>
          <div className="chat-header-divider" />
        </header>

        <main className={`chat-main${layout === 'planner' ? ' layout-planner' : ''}`}>
          <div className={`chat-wrapper${layout === 'planner' ? ' chat-wrapper-narrow' : ''}`}>
            <img ref={chatHawkRef} src={MASCOT_SRCS.flight} alt="HAWKwarts"
              className={`chat-hawk${phase === 'chat' ? ' chat-hawk-flying' : ''}`}
              style={{ opacity: chatHawkHidden ? 0 : 1 }} />
            <div className="chat-container">
              <div className="chat-messages">
                {messages.length === 0 ? (
                  <div className="chat-empty">
                    <p className="chat-empty-heading">What can I help you with?</p>
                    <p className="chat-empty-sub">Ask about courses, registration, degree planning, or campus life.</p>
                    <div className="chat-suggestions">
                      {SUGGESTED_PROMPTS.map(prompt => (
                        <button key={prompt} className="chat-suggestion"
                          onClick={() => {
                            setInput(prompt);
                            if (PLANNING_RE.test(prompt)) {
                              setLayout('planner');
                              setMessages(PLANNER_MESSAGES);
                            }
                          }}>
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((msg, i) => (
                    <div key={i} className={`message message-${msg.from}`}>
                      <span className="message-label">
                        {msg.from === 'hawkwarts' ? 'HAWKwarts' : 'You'}
                      </span>
                      <p className="message-text">{msg.text}</p>
                      {msg.cards && (
                        <div className="course-cards">
                          {msg.cards.map(card => (
                            <div key={card.code} className="course-card">
                              <div className="course-card-top">
                                <div className="course-card-identity">
                                  <span className="course-code">{card.code}</span>
                                  <span className="course-name">{card.name}</span>
                                </div>
                                <span className="course-credits">{card.credits} cr.</span>
                              </div>
                              <p className="course-desc">{card.description}</p>
                              <div className="course-tags">
                                {card.tags.map(tag => <span key={tag} className="course-tag">{tag}</span>)}
                              </div>
                              <div className="course-prereqs">
                                <span className="course-prereqs-label">Prereq:</span> {card.prereqs}
                              </div>
                              <div className="course-actions">
                                <button className="course-btn-secondary">View details</button>
                                <button className="course-btn-primary">Add to plan</button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              <div className="chat-input-row">
                <input className="chat-input" type="text" placeholder="Ask HAWKwarts..."
                  value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} />
                <button className="chat-send-btn" onClick={() => sendMessage()} aria-label="Send message">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                    strokeLinejoin="round" aria-hidden="true">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {layout === 'planner' && <ScheduleBuilder />}
        </main>

        <Disclaimer />

        <button className="chat-back-btn" onClick={goToLanding}>&#8592; Back</button>
      </div>
    </div>
  );
}
