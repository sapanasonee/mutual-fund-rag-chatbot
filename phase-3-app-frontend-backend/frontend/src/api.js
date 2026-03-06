const API_BASE = ''

export async function sendChat(query, conversationHistory = []) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      conversation_history: conversationHistory.map(m => ({
        role: m.role,
        content: m.content,
      })),
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function searchFunds(q = '') {
  const params = new URLSearchParams(q ? { q } : {})
  const res = await fetch(`${API_BASE}/search-funds?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getFund(schemeId) {
  const res = await fetch(`${API_BASE}/funds/${encodeURIComponent(schemeId)}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
