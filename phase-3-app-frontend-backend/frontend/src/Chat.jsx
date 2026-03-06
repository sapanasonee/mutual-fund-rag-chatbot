import { useState, useRef, useEffect } from 'react'

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
          isUser
            ? 'bg-amber-600/80 text-white'
            : 'bg-slate-700/80 text-slate-100'
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
      </div>
    </div>
  )
}

function Chat({ messages, loading, onSend }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return
    onSend(input)
    setInput('')
  }

  return (
    <div className="flex flex-col rounded-xl border border-slate-700 bg-slate-800/30">
      <div className="max-h-[480px] overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="py-8 text-center text-slate-500">
            Type a question or use a quick action above.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className="mb-3">
            <Message msg={m} />
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-slate-700/80 px-4 py-2.5">
              <span className="text-sm text-slate-400">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} className="border-t border-slate-700 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about mutual funds..."
            className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-amber-500/60 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-amber-600 px-5 py-2.5 font-medium text-white transition hover:bg-amber-500 disabled:opacity-50 disabled:hover:bg-amber-600"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}

export default Chat
