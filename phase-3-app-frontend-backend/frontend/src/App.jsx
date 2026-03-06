import { useState } from 'react'
import Chat from './Chat'

const QUICK_ACTIONS = [
  'What is the expense ratio of HDFC Small Cap Fund?',
  'Show key metrics for HDFC Flexi Cap Fund',
  'What is the riskometer of SBI Contra Fund?',
  'How to download mutual fund account statements?',
  'What is a riskometer?',
  'Compare HDFC ELSS Tax Saver with HDFC Small Cap',
]

function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  const handleSend = async (query) => {
    if (!query?.trim()) return
    const userMsg = { role: 'user', content: query.trim() }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    try {
      const history = [...messages, userMsg].slice(-10)
      const data = await (await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          conversation_history: history.slice(0, -1),
        }),
      })).json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}. Make sure the backend is running on ${process.env.BACKEND_URL}.`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleQuickAction = (text) => {
    handleSend(text)
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-800/50 px-6 py-4">
        <h1 className="text-xl font-semibold">Mutual Fund Chatbot</h1>
        <p className="mt-1 text-sm text-slate-400">
          Ask about expense ratio, exit load, minimum SIP, riskometer, benchmark, lock-in, portfolio, or how to download statements.
        </p>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <div className="mb-4">
          <p className="mb-2 text-sm text-slate-400">Quick actions</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_ACTIONS.map((text) => (
              <button
                key={text}
                onClick={() => handleQuickAction(text)}
                className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-slate-300 transition hover:border-amber-500/60 hover:bg-slate-700 hover:text-amber-100"
              >
                {text}
              </button>
            ))}
          </div>
        </div>
        <Chat
          messages={messages}
          loading={loading}
          onSend={handleSend}
        />
      </main>
    </div>
  )
}

export default App
