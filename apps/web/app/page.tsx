"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
};

const API_URL = process.env.NEXT_PUBLIC_RICO_API || "http://localhost:8000";

function uuid() {
  return Math.random().toString(36).slice(2);
}

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: uuid(),
      role: "assistant",
      content:
        "I’m Rico. I can track jobs, remember preferences, detect opportunities, and help manage your applications.",
      createdAt: new Date().toISOString(),
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMessage: Message = {
      id: uuid(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: "web-user",
          message: trimmed,
        }),
      });

      const data = await response.json();

      const assistantMessage: Message = {
        id: uuid(),
        role: "assistant",
        content:
          data.reply ||
          data.message ||
          "Rico processed your request.",
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const assistantMessage: Message = {
        id: uuid(),
        role: "assistant",
        content:
          "Rico could not reach the backend API. Start the FastAPI server and verify NEXT_PUBLIC_RICO_API.",
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setLoading(false);
    }
  }

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  return (
    <main style={{ minHeight: "100vh", background: "#0b1020", color: "#f5f7fb" }}>
      <div
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: "32px 16px",
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
      >
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0, fontSize: 36 }}>Rico AI</h1>
          <p style={{ opacity: 0.8 }}>
            Persistent autonomous career assistant
          </p>
        </header>

        <section
          style={{
            flex: 1,
            overflowY: "auto",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 16,
            padding: 16,
            background: "rgba(255,255,255,0.03)",
          }}
        >
          {messages.map((message) => (
            <div
              key={message.id}
              style={{
                display: "flex",
                justifyContent:
                  message.role === "user" ? "flex-end" : "flex-start",
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  maxWidth: "80%",
                  padding: "14px 16px",
                  borderRadius: 14,
                  background:
                    message.role === "user"
                      ? "#4f46e5"
                      : "rgba(255,255,255,0.08)",
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                }}
              >
                {message.content}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ opacity: 0.7, padding: 8 }}>
              Rico is thinking…
            </div>
          )}

          <div ref={bottomRef} />
        </section>

        <footer
          style={{
            marginTop: 16,
            display: "flex",
            gap: 12,
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Rico about jobs, applications, interviews, or strategy…"
            rows={3}
            style={{
              flex: 1,
              borderRadius: 12,
              padding: 14,
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(255,255,255,0.05)",
              color: "white",
              resize: "none",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
          />

          <button
            onClick={sendMessage}
            disabled={!canSend}
            style={{
              minWidth: 120,
              borderRadius: 12,
              border: "none",
              cursor: canSend ? "pointer" : "not-allowed",
              opacity: canSend ? 1 : 0.5,
            }}
          >
            Send
          </button>
        </footer>
      </div>
    </main>
  );
}
