"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Sparkles } from "lucide-react";

const SUGGESTED_QUESTIONS = [
  "Which medicines need immediate attention?",
  "How much should we order?",
  "Where can we redistribute stock from?",
  "What should we prioritize during an emergency?",
];

interface Message {
  role: "user" | "assistant";
  text: string;
  source?: "gemini" | "fallback";
}

export function AiAssistantPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const ask = async (question: string) => {
    if (!question.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.askAssistant(question);
      setMessages((prev) => [...prev, { role: "assistant", text: res.answer, source: res.source }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Could not reach the backend. Is the Django server running?" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-sky-400" />
          AI Assistant
        </CardTitle>
      </CardHeader>
      <CardContent>
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => ask(q)}
                className="text-xs rounded-full border border-slate-700 px-3 py-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-3 max-h-80 overflow-y-auto mb-3">
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "text-right" : ""}>
              <div
                className={
                  m.role === "user"
                    ? "inline-block bg-sky-600/20 text-sky-100 rounded-lg px-3 py-2 text-sm max-w-[85%]"
                    : "inline-block bg-slate-800/60 text-slate-300 rounded-lg px-3 py-2 text-sm max-w-[85%] whitespace-pre-line text-left"
                }
              >
                {m.text}
                {m.source === "fallback" && (
                  <div className="text-[10px] text-slate-500 mt-1">Rule-based fallback (no Gemini API key configured)</div>
                )}
              </div>
            </div>
          ))}
          {loading && <div className="text-xs text-slate-500">Thinking...</div>}
        </div>

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(input)}
            placeholder="Ask about risk, procurement, redistribution..."
            className="flex-1 rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-600"
          />
          <Button onClick={() => ask(input)} disabled={loading}>
            Ask
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
