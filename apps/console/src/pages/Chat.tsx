import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { streamChat } from "../api";

interface Msg {
  role: "user" | "assistant";
  text: string;
  runId?: string;
  status?: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [pendingTools, setPendingTools] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollDown = () =>
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
    });

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }]);
    scrollDown();
    try {
      for await (const event of streamChat(text, conversationRef.current)) {
        if (event.type === "conversation") {
          conversationRef.current = event.conversation_id as string;
        } else if (event.type === "tool_call") {
          setPendingTools((event.tools as string[]) ?? []);
        } else if (event.type === "tool_result") {
          setPendingTools([]);
        } else if (event.type === "final") {
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              text: (event.text as string) || "(no reply)",
              runId: event.run_id as string,
              status: event.status as string,
            },
          ]);
        } else if (event.type === "error") {
          setError(event.message as string);
        }
        scrollDown();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setPendingTools([]);
      setBusy(false);
      scrollDown();
    }
  }

  return (
    <>
      <h1>Chat</h1>
      <p className="subtitle">
        Talk to the live triage agent. Every reply links to its step-level trace. Try:
        “My account is ACCT-1002. Video shows a black screen but audio keeps playing.”
      </p>
      {error && <div className="error-banner">{error}</div>}
      <div className="card chat-box">
        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 && (
            <p className="dim">
              No messages yet. Seeded accounts to try: ACCT-1002 (old WebView), ACCT-1003
              (consent reset), ACCT-1007 (imported vehicle), ACCT-1011 (fleet auth expired).
            </p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`msg ${msg.role}`}>
              {msg.text}
              {msg.runId && (
                <span className="runlink">
                  {msg.status && msg.status !== "final" && (
                    <span className="badge warn">{msg.status}</span>
                  )}{" "}
                  <Link to={`/traces/${msg.runId}`}>view trace</Link>
                </span>
              )}
            </div>
          ))}
          {pendingTools.length > 0 && (
            <div className="chip-row">
              {pendingTools.map((tool) => (
                <span key={tool} className="chip">⚙ {tool}…</span>
              ))}
            </div>
          )}
          {busy && pendingTools.length === 0 && <p className="dim">thinking…</p>}
        </div>
        <div className="chat-input">
          <input
            value={input}
            placeholder="Describe the customer's issue…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={busy}
          />
          <button className="primary" onClick={send} disabled={busy || !input.trim()}>
            Send
          </button>
          <button
            onClick={() => {
              conversationRef.current = null;
              setMessages([]);
              setError(null);
            }}
            disabled={busy}
          >
            New conversation
          </button>
        </div>
      </div>
    </>
  );
}
