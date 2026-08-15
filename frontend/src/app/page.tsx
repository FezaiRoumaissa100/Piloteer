"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";

type Message = {
  id: string;
  type: "user" | "agent" | "system" | "success" | "error" | "ask_user" | "cancelled";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isTaskRunning, setIsTaskRunning] = useState(false);
  const [isWaitingForReply, setIsWaitingForReply] = useState(false);
  const [hitlAction, setHitlAction] = useState<string | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => scrollToBottom(), [messages, isTaskRunning, hitlAction]);

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(`ws://localhost:8000/ws`);
      
      ws.current.onopen = () => setIsConnected(true);
      ws.current.onclose = () => {
        setIsConnected(false);
        setIsTaskRunning(false);
        setHitlAction(null);
      };
      
      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const { type, content } = data;
        
        if (type === "system") return;

        if (type === "ask_user") {
          if (typeof content === "string" && content.startsWith("HITL:")) {
            const actionDesc = content.replace("HITL:", "").trim();
            setHitlAction(actionDesc);
            setIsWaitingForReply(true);
            return; // Do not add to chat messages stream
          } else {
            setIsWaitingForReply(true);
          }
        } else if (type === "success" || type === "error" || type === "cancelled") {
          setIsTaskRunning(false);
          setIsWaitingForReply(false);
          setHitlAction(null);
        }

        setMessages((prev) => [...prev, { id: Date.now().toString() + Math.random(), type, content }]);
      };
    };

    connect();
    return () => ws.current?.close();
  }, []);

  const handleSend = () => {
    if (!input.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) return;
    
    setMessages((prev) => [...prev, { id: Date.now().toString(), type: "user", content: input }]);
    ws.current.send(input);
    setInput("");
    
    if (isWaitingForReply) {
      setIsWaitingForReply(false);
      setIsTaskRunning(true);
    } else {
      setIsTaskRunning(true);
    }
  };

  const handleHitlDecision = (decision: "allow" | "deny") => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    ws.current.send(decision);
    setHitlAction(null);
    setIsWaitingForReply(false);
    setIsTaskRunning(true);

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        type: "user",
        content: decision === "allow" ? "Allowed risky action." : "Denied risky action."
      }
    ]);
  };

  const handleCancel = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;
    ws.current.send("__CANCEL__");
    setHitlAction(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  return (
    <div className="flex flex-col h-screen bg-white text-gray-800 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-black flex items-center justify-center text-white font-bold">
            P
          </div>
          <h1 className="font-semibold text-lg">Piloteer</h1>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      {/* Main Messages Container */}
      <main className="flex-1 overflow-y-auto px-4 md:px-24 lg:px-64 py-8 space-y-6">
        {messages.map((msg) => {
          if (msg.type === "cancelled") {
            return (
              <div key={msg.id} className="w-full flex items-center justify-center my-4">
                <span className="text-xs text-gray-400 bg-gray-50 border border-gray-200 px-3 py-1 rounded-full font-medium">
                  The user cancelled the task
                </span>
              </div>
            );
          }

          return (
            <div key={msg.id} className={`flex gap-4 ${msg.type === "user" ? "flex-row-reverse" : "flex-row"}`}>
              <div className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-sm ${msg.type === "user" ? "bg-gray-200 text-gray-700" : "bg-[#10a37f] text-white"}`}>
                {msg.type === "user" ? "U" : "P"}
              </div>
              <div className={`max-w-[75%] px-4 py-3 rounded-2xl ${msg.type === "user" ? "bg-gray-100 rounded-tr-none" : "bg-white border border-gray-100 rounded-tl-none shadow-sm"}`}>
                <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}
        {isTaskRunning && !isWaitingForReply && (
          <div className="flex gap-4">
            <div className="w-8 h-8 shrink-0 rounded-full bg-[#10a37f] text-white flex items-center justify-center text-sm">P</div>
            <div className="flex items-center gap-1 text-gray-400 px-4 py-3">
              <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce"></div>
              <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: "0.2s" }}></div>
              <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: "0.4s" }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input & HITL Warning Section */}
      <div className="px-4 md:px-24 lg:px-64 pb-6 pt-2 bg-gradient-to-t from-white via-white to-transparent">
        <div className="max-w-3xl mx-auto space-y-3">
          {/* Antigravity-Style Soft Red HITL Alert Box Above Input Bar */}
          {hitlAction && (
            <div className="p-4 bg-red-50/90 border border-red-200 rounded-2xl shadow-sm backdrop-blur-sm flex items-center justify-between gap-4 animate-fadeIn">
              <div className="flex items-center gap-3">
                <span className="px-2 py-0.5 text-[10px] font-bold tracking-wider text-red-700 bg-red-100/80 rounded border border-red-200 uppercase shrink-0">
                  SECURITY ALERT
                </span>
                <p className="text-sm font-medium text-red-950 leading-snug">
                  The agent wants to <span className="font-semibold text-red-800">'{hitlAction}'</span>. Respond if you allow or deny this.
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => handleHitlDecision("allow")}
                  className="px-3.5 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-xl hover:bg-red-700 active:scale-95 transition-all shadow-sm"
                >
                  Allow
                </button>
                <button
                  onClick={() => handleHitlDecision("deny")}
                  className="px-3.5 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 active:scale-95 transition-all shadow-sm"
                >
                  Deny
                </button>
              </div>
            </div>
          )}

          {/* Standard Input Box */}
          <div className="relative flex items-end bg-white border border-gray-300 rounded-2xl shadow-[0_0_15px_rgba(0,0,0,0.05)] overflow-hidden focus-within:border-gray-400 transition-colors">
            <textarea
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              disabled={!isConnected || (isTaskRunning && !isWaitingForReply) || !!hitlAction}
              placeholder={
                hitlAction
                  ? "Please respond to the security alert above..."
                  : isWaitingForReply
                  ? "Type your reply..."
                  : "Message Piloteer..."
              }
              className="w-full max-h-48 py-4 pl-4 pr-12 bg-transparent border-none outline-none resize-none text-[15px] disabled:opacity-50 disabled:bg-gray-50"
              rows={1}
            />
            <div className="absolute right-2 bottom-2">
              {isTaskRunning && !isWaitingForReply ? (
                <button onClick={handleCancel} className="p-2 mb-1 bg-black rounded-lg text-white hover:bg-gray-800 transition-colors" title="Cancel Task">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>
                </button>
              ) : (
                <button 
                  onClick={handleSend} 
                  disabled={!input.trim() || !isConnected || !!hitlAction}
                  className="p-2 mb-1 bg-black rounded-lg text-white disabled:bg-gray-300 disabled:text-gray-500 hover:bg-gray-800 transition-colors"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
                </button>
              )}
            </div>
          </div>
        </div>
        <p className="text-center text-xs text-gray-400 mt-3">Piloteer can make mistakes. Check important actions.</p>
      </div>
    </div>
  );
}
