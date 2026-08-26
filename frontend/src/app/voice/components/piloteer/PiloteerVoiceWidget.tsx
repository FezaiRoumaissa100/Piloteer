"use client";

import React, { useRef, useState } from "react";
import { Mic, Square, MessageSquare, Volume2 } from "lucide-react";
import Link from "next/link";

/**
 * PiloteerVoiceWidget
 *
 * The browser owns microphone capture. FastAPI owns the /ws/voice bridge.
 * Gemini remains the STT/TTS transport and Piloteer remains the decision-maker.
 * Recording is deliberately manual: first click starts, second click sends
 * speech_end. There is no automatic VAD timeout in this component.
 */
const VOICE_WS_URL = "ws://localhost:8000/ws/voice";
const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;

type AgentState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "awaiting_user"
  | "error";

const FREQUENCY_WEIGHTS = [
  0.32, 0.52, 0.78, 0.46, 0.92, 0.62, 1, 0.58, 0.88, 0.42, 0.72, 0.5, 0.3,
];

export default function PiloteerVoiceWidget() {
  const [agentState, setAgentState] = useState<AgentState>("idle");

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const nextPlaybackTimeRef = useRef(0);
  const startingRef = useRef(false);
  const activeAudioSourcesRef = useRef(0);
  const audioIdleTimerRef = useRef<number | null>(null);

  const [isAudioPlaying, setIsAudioPlaying] = useState(false);

  const downsampleTo16kHz = (
    buffer: Float32Array,
    sampleRate: number,
  ): ArrayBuffer => {
    const ratio = sampleRate / INPUT_SAMPLE_RATE;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Int16Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let sum = 0;
      let count = 0;

      for (
        let i = offsetBuffer;
        i < nextOffsetBuffer && i < buffer.length;
        i++
      ) {
        sum += buffer[i];
        count++;
      }

      const sample = count > 0 ? sum / count : 0;
      result[offsetResult] = Math.max(-1, Math.min(1, sample)) * 0x7fff;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }

    return result.buffer;
  };

  const playPcm16Chunk = (pcmData: Int16Array) => {
    if (!audioContextRef.current || pcmData.length === 0) return;

    const ctx = audioContextRef.current;
    const buffer = ctx.createBuffer(1, pcmData.length, OUTPUT_SAMPLE_RATE);
    const channelData = buffer.getChannelData(0);

    for (let i = 0; i < pcmData.length; i++) {
      channelData[i] = pcmData[i] / 0x7fff;
    }

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    activeAudioSourcesRef.current += 1;
    if (audioIdleTimerRef.current !== null) {
      window.clearTimeout(audioIdleTimerRef.current);
      audioIdleTimerRef.current = null;
    }
    setIsAudioPlaying(true);

    const startTime = Math.max(ctx.currentTime, nextPlaybackTimeRef.current);
    source.onended = () => {
      activeAudioSourcesRef.current = Math.max(
        0,
        activeAudioSourcesRef.current - 1,
      );

      if (activeAudioSourcesRef.current === 0) {
        audioIdleTimerRef.current = window.setTimeout(() => {
          audioIdleTimerRef.current = null;
          setIsAudioPlaying(false);
        }, 90);
      }
    };
    source.start(startTime);
    nextPlaybackTimeRef.current = startTime + buffer.duration;
  };

  const playAudioChunk = (base64Data: string) => {
    const binaryString = window.atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);

    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    playPcm16Chunk(new Int16Array(bytes.buffer));
  };

  const releaseMicrophone = () => {
    scriptNodeRef.current?.disconnect();
    scriptNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  };

  /** Explicitly finishes the user's turn. No silence timer or automatic VAD. */
  const finishRecording = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "speech_end" }));
    }

    releaseMicrophone();
    setAgentState("processing");
  };

  const startMicrophoneCapture = async (ws: WebSocket) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      mediaStreamRef.current = stream;

      const ctx = audioContextRef.current!;
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      scriptNodeRef.current = processor;

      processor.onaudioprocess = (event) => {
        if (ws.readyState !== WebSocket.OPEN) return;

        const inputData = event.inputBuffer.getChannelData(0);
        ws.send(downsampleTo16kHz(inputData, ctx.sampleRate));
      };

      source.connect(processor);

      const silentGain = ctx.createGain();
      silentGain.gain.value = 0;
      processor.connect(silentGain);
      silentGain.connect(ctx.destination);

      startingRef.current = false;
    } catch (error) {
      console.error("Microphone error", error);
      releaseMicrophone();
      startingRef.current = false;
      setAgentState("error");
    }
  };

  const connectVoiceSocket = () => {
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return wsRef.current;
    }

    const ws = new WebSocket(VOICE_WS_URL);
    wsRef.current = ws;
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
    };

    ws.onmessage = (event) => {
      try {
        if (event.data instanceof ArrayBuffer) {
          playPcm16Chunk(new Int16Array(event.data));
          return;
        }

        if (typeof event.data !== "string") return;
        const msg = JSON.parse(event.data);

        if (msg.type === "state") {
          const nextState = msg.content as AgentState;
          setAgentState(nextState);
        } else if (msg.type === "audio") {
          playAudioChunk(msg.data);
        } else if (msg.type === "error") {
          releaseMicrophone();
          setAgentState("error");
        }
      } catch (error) {
        console.error("Erreur parsing WS", error);
      }
    };

    ws.onclose = () => {
      startingRef.current = false;
      releaseMicrophone();
      if (wsRef.current === ws) wsRef.current = null;
      activeAudioSourcesRef.current = 0;
      if (audioIdleTimerRef.current !== null) {
        window.clearTimeout(audioIdleTimerRef.current);
        audioIdleTimerRef.current = null;
      }
      setIsAudioPlaying(false);
      setAgentState("idle");
    };

    return ws;
  };

  const toggleMic = async () => {
    if (
      startingRef.current ||
      agentState === "processing" ||
      agentState === "speaking" ||
      isAudioPlaying
    )
      return;

    if (agentState === "listening") {
      finishRecording();
      return;
    }

    if (
      agentState !== "idle" &&
      agentState !== "error" &&
      agentState !== "awaiting_user"
    )
      return;

    startingRef.current = true;

    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext)();
    }
    await audioContextRef.current.resume();

    const ws = connectVoiceSocket();
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "start" }));
      await startMicrophoneCapture(ws);
      return;
    }

    const waitForOpen = () => {
      if (ws.readyState !== WebSocket.OPEN) {
        startingRef.current = false;
        setAgentState("error");
        return;
      }
      ws.send(JSON.stringify({ type: "start" }));
      void startMicrophoneCapture(ws);
    };

    ws.addEventListener("open", waitForOpen, { once: true });
  };

  React.useEffect(() => {
    const ws = connectVoiceSocket();

    return () => {
      releaseMicrophone();
      ws.close();
      if (wsRef.current === ws) wsRef.current = null;
    };
  }, []);

  const isListening = agentState === "listening";
  const isSpeaking = agentState === "speaking";
  const isSpeakingVisual = isSpeaking || isAudioPlaying;
  const isProcessing = agentState === "processing";
  const isAwaitingUser = agentState === "awaiting_user";
  return (
    <>
      <style>{`
        @keyframes piloteer-natural-blink {
          0%, 92%, 100% {
            transform: scaleY(1);
          }
          94%, 97% {
            transform: scaleY(0.08);
          }
        }
        .piloteer-natural-blink {
          animation: piloteer-natural-blink 6.5s ease-in-out infinite;
          transform-origin: center;
          will-change: transform;
        }
        .piloteer-speaking-eye-arc {
          display: block;
          height: 0.55rem;
          width: 1rem;
          border-top: 3px solid white;
          border-radius: 50% 50% 0 0;
          transform: translateY(0.12rem);
        }
        @keyframes piloteer-speaking-breathe {
          0%, 100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.035);
          }
        }
        .piloteer-speaking-breathe {
          animation: piloteer-speaking-breathe 1.35s ease-in-out infinite;
          transform-origin: center;
          will-change: transform;
        }
        @media (prefers-reduced-motion: reduce) {
          .piloteer-natural-blink,
          .piloteer-speaking-breathe {
            animation: none;
          }
        }
      `}</style>
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white px-6 py-10 text-slate-900">
        <div
          aria-hidden="true"
          className={`pointer-events-none absolute left-1/2 top-1/2 h-[18rem] w-[18rem] -translate-x-1/2 -translate-y-1/2 rounded-full border ${isListening ? "border-emerald-300/24 bg-emerald-200/10 shadow-[0_0_28px_6px_rgba(52,211,153,0.15)]" : isProcessing ? "border-sky-300/24 bg-sky-200/10 shadow-[0_0_26px_5px_rgba(125,211,252,0.13)]" : "border-emerald-200/24 bg-emerald-100/9 shadow-[0_0_22px_4px_rgba(110,231,183,0.1)]"}`}
        />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-20 top-1/4 h-64 w-64 rounded-full border border-teal-200/25 bg-teal-100/10"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-16 bottom-1/4 h-72 w-72 rounded-full border border-lime-200/25 bg-lime-100/10"
        />

        <section className="relative z-10 flex w-full max-w-2xl flex-col items-center">
          <div className="relative flex h-[22rem] w-full items-center justify-center sm:h-[26rem]">
            <div
              aria-hidden="true"
              className="absolute h-64 w-64 rounded-full border border-emerald-400/24 will-change-transform"
            />
            <div
              aria-hidden="true"
              className="absolute h-80 w-52 rounded-[50%] border border-teal-400/22 will-change-transform"
            />
            <button
              type="button"
              onClick={toggleMic}
              aria-label={
                isListening ? "Finish voice message" : "Start voice interaction"
              }
              title={
                isListening
                  ? "Click to finish your voice message"
                  : "Click to start recording"
              }
              className="relative z-10 flex h-48 w-48 items-center justify-center rounded-full outline-none will-change-transform sm:h-56 sm:w-56"
            >
              <span
                aria-hidden="true"
                className={`absolute inset-[-0.7rem] rounded-full blur-sm ${isListening ? "bg-emerald-400/62" : isProcessing ? "bg-sky-400/52" : "bg-emerald-400/42"}`}
              />
              <span
                aria-hidden="true"
                className="absolute inset-[-0.3rem] rounded-full bg-[conic-gradient(from_20deg,#0f766e,#34d399,#bef264,#14b8a6,#0f766e)] opacity-70 blur-[1px]"
              />
              <span
                className={`relative flex h-full w-full items-center justify-center overflow-hidden rounded-full border border-white/52 bg-[radial-gradient(circle_at_30%_22%,#d9f99d_0%,#6ee7b7_27%,#10b981_57%,#047857_100%)] will-change-transform ${isSpeakingVisual ? "piloteer-speaking-breathe" : ""} ${isListening ? "shadow-[inset_10px_12px_24px_rgba(255,255,255,0.48),inset_-18px_-25px_35px_rgba(4,120,87,0.38),0_5px_14px_rgba(16,185,129,0.11)]" : "shadow-[inset_10px_12px_24px_rgba(255,255,255,0.48),inset_-18px_-25px_35px_rgba(4,120,87,0.38),0_3px_10px_rgba(16,185,129,0.06)]"}`}
              >
                <span
                  aria-hidden="true"
                  className="absolute -left-8 top-2 h-32 w-20 rotate-[28deg] rounded-full bg-white/25 blur-sm"
                />
                <span
                  aria-hidden="true"
                  className="absolute -bottom-10 right-0 h-28 w-36 rounded-full bg-teal-950/20 blur-lg"
                />

                <div className="relative z-10 flex items-center gap-7">
                  {isSpeakingVisual
                    ? [0, 1].map((eye) => (
                        <span
                          key={eye}
                          className="piloteer-speaking-eye-arc"
                          aria-hidden="true"
                        />
                      ))
                    : [0, 1].map((eye) => (
                        <span
                          key={eye}
                          className={`block h-4 w-3 rounded-full bg-white piloteer-natural-blink ${isListening ? "shadow-[0_0_18px_rgba(255,255,255,0.98)]" : "shadow-[0_0_12px_rgba(255,255,255,0.82)]"}`}
                        />
                      ))}
                </div>
              </span>
            </button>
          </div>

          <div
            className="mt-5 flex h-10 items-center justify-center gap-1.5"
            aria-hidden="true"
          >
            {FREQUENCY_WEIGHTS.map((weight, index) => (
              <span
                key={index}
                className={`block w-1 rounded-full ${isListening ? "bg-emerald-500/80" : isSpeakingVisual ? "bg-teal-500/80" : "bg-emerald-300/65"}`}
                style={{ height: `${6 + weight * 12}px` }}
              />
            ))}
          </div>

          <div className="mt-12 flex items-center gap-16">
            <button
              type="button"
              onClick={toggleMic}
              aria-label={
                isListening
                  ? "Finish voice message"
                  : isSpeaking
                    ? "Piloteer is speaking"
                    : isAwaitingUser
                      ? "Answer Piloteer"
                      : "Start voice recording"
              }
              title={
                isListening
                  ? "Click to finish your voice message"
                  : isSpeaking
                    ? "Piloteer is speaking"
                    : isAwaitingUser
                      ? "Click to answer Piloteer"
                      : "Click to start speaking"
              }
              className={`flex h-12 w-12 items-center justify-center rounded-full border transition-colors ${isListening ? "border-emerald-300 bg-emerald-50 text-emerald-600 shadow-[0_0_24px_rgba(52,211,153,0.3)]" : isSpeaking ? "border-teal-300 bg-teal-50 text-teal-600 shadow-[0_0_24px_rgba(45,212,191,0.3)]" : "border-slate-200 bg-white text-slate-500 shadow-sm hover:border-emerald-300 hover:text-emerald-600"}`}
            >
              {isListening ? (
                <Square className="h-4 w-4 fill-current" />
              ) : isSpeaking ? (
                <Volume2 className="h-5 w-5" />
              ) : (
                <Mic className="h-5 w-5" />
              )}
            </button>
            <Link
              href="/"
              aria-label="Chat mode"
              className="flex h-12 w-12 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:border-emerald-300 hover:text-emerald-600"
            >
              <MessageSquare className="h-5 w-5" />
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
