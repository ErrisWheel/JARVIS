import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Brain, Code2, Cpu, Database, Download, Globe2, HardDrive, Mic, MicOff, Orbit, Send, ShieldCheck, Sparkles, StopCircle, Trash2, X, RefreshCw, ChevronDown, Pencil, Plus, MessageSquare, TerminalSquare, LoaderCircle } from 'lucide-react';
import Hologram from './Hologram';
import DevelopmentLab from './DevelopmentLab';
import { extractImageGenerationPrompt, extractExplicitPosterGenerationPrompt, extractContextualImageGenerationPrompt, extractContextualPosterRedesignRequest, isGeneratedImageFollowUp, isUnverifiedImageCreationClaim, type PosterDesignVariant } from './imageIntent';
import { api, type ActivityNode, type Hardware, type Memory, type ModelInfo, type VoiceDevice, type VoiceEvent, type StyleProfile, type MicTelemetry, type OperatorInstruction, type ImageProgressEvent, type ModelTeamStatus } from './api';

type ImageProgress = { stage: string; label: string; percent: number | null; step?: number; totalSteps?: number; elapsedSeconds: number; etaSeconds: number | null };
type ChatLine = { role: 'user' | 'assistant'; content: string; imageUrl?: string; imageFilename?: string; svgFilename?: string; imagePrompt?: string; posterSourcePrompt?: string; isPoster?: boolean; designVariant?: PosterDesignVariant; imageProgress?: ImageProgress };
type Mode = 'assistant' | 'teaching' | 'interview' | 'practice' | 'review' | 'correction';
const modes: { id: Mode; label: string }[] = [
  { id: 'assistant', label: 'Assistant' }, { id: 'teaching', label: 'Teaching' }, { id: 'interview', label: 'Interview' },
  { id: 'practice', label: 'Practice' }, { id: 'review', label: 'Review' }, { id: 'correction', label: 'Correction' },
];
const conversationId = 'main';
const initialActivityNodes: ActivityNode[] = [
  { id: 'input', status: 'idle', title: 'Waiting for input', summary: 'Conversation input is idle.', details: 'When conversation mode is enabled, local voice activity detection monitors the selected microphone. Only direct questions and commands are routed to JARVIS.' },
  { id: 'memory', status: 'idle', title: 'Context and memory', summary: 'Waiting for a request to identify relevant context.', details: 'This node reports how much recent conversation and how many saved SQLite memories were actually supplied to the model.' },
  { id: 'model', status: 'idle', title: 'Model team and answer basis', summary: 'The lead model and independent reviewer are standing by.', details: 'Substantive requests are reviewed by a second local text model before the lead model composes the response. Vision and image-generation engines are routed to their specialist tasks. GPU inference is serialized to protect VRAM.' },
  { id: 'response', status: 'idle', title: 'Answer output', summary: 'No answer is being generated.', details: 'This node reports when the response starts, streams, completes or is interrupted.' },
];

function fmt(value: number | null | undefined, suffix = '') { return value == null || Number.isNaN(value) ? '—' : `${Math.round(value * 10) / 10}${suffix}`; }

function extractGeneratedImageReference(content: string): { filename: string; content: string; isPoster: boolean; designVariant?: PosterDesignVariant } | null {
  const marker = content.match(/\[\[JARVIS_IMAGE:([0-9a-f]{32}\.png)\]\]/i);
  const designMarker = content.match(/\[\[JARVIS_POSTER_DESIGN:(cards|timeline|orbit|blueprint|museum|fieldnotes|collage)\]\]/i);
  const isPoster = Boolean(designMarker || /Rendered locally with precise typography/i.test(content));
  const designVariant = (designMarker?.[1]?.toLowerCase() as PosterDesignVariant | undefined) || (isPoster ? 'cards' : undefined);
  if (marker?.[1]) {
    const cleaned = content.replace(marker[0], '').replace(designMarker?.[0] || '', '').trim();
    return { filename: marker[1], content: cleaned, isPoster, designVariant };
  }
  // Accept only same-machine JARVIS image routes; never fetch arbitrary model-provided URLs.
  const localUrl = content.match(/(?:https?:\/\/(?:127\.0\.0\.1|localhost):5173)?\/api\/generated-images\/([0-9a-f]{32}\.png)(?:[?#][^\s)]*)?/i);
  if (!localUrl?.[1]) return null;
  const filename = localUrl[1];
  const markdownLink = new RegExp(
    String.raw`\[[^\]]*\]\((?:https?:\/\/(?:127\.0\.0\.1|localhost):5173)?\/api\/generated-images\/${filename}(?:[?#][^)]*)?\)`,
    'i',
  );
  const cleaned = content.replace(markdownLink, '').replace(localUrl[0], '').replace(designMarker?.[0] || '', '').trim();
  return { filename, content: cleaned, isPoster, designVariant };
}

function recoverPosterSourcePrompt(imagePrompt: string): string {
  const marker = 'ORIGINAL OPERATOR BRIEF TO PRESERVE:';
  const index = imagePrompt.lastIndexOf(marker);
  return (index >= 0 ? imagePrompt.slice(index + marker.length) : imagePrompt).trim().slice(0, 12000);
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return '—';
  const safe = Math.max(0, Math.round(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`;
}

function shouldUseProgressSpeech(message: string): boolean {
  const normalized = message.toLowerCase().replace(/[^\p{L}\p{N}'’ -]/gu, ' ').replace(/\s+/g, ' ').trim();
  if (!normalized) return false;

  // These are conversational checks, greetings, acknowledgements, or short factual questions.
  // They should receive the answer directly, without an artificial "On it" preamble.
  const quickIntent = /^(?:can you hear me(?: now)?|can you hear that|are you there|are you listening|do you hear me|hello|hi|hey|good morning|good afternoon|good evening|how are you|what is your name|what's your name|who are you|who created you|who built you|thank you|thanks|okay|ok|yes|no|test voice|testing)(?: jarvis)?[.!? ]*$/i;
  if (quickIntent.test(normalized)) return false;

  const words = normalized.split(' ').filter(Boolean);
  const substantialTask = /\b(?:build|create|design|implement|debug|fix|troubleshoot|investigate|research|compare|analy[sz]e|summari[sz]e|plan|write|draft|generate|refactor|configure|install|update|rewrite|review|inspect|trace|migrate|deploy|organize|patch|test|make it|change it|step by step|help me|look into|figure out)\b/i.test(normalized);
  if (substantialTask) return true;
  return words.length >= 22 || normalized.length >= 150;
}

function splitSpeechSegments(buffer: string, flush = false): { segments: string[]; remainder: string } {
  const segments: string[] = [];
  let remaining = buffer;
  const MIN_CLAUSE_CHARS = 24;
  const MAX_SEGMENT_CHARS = 68;

  while (remaining.length) {
    let fencedCode = false;
    let inlineCode = false;
    let boundary = -1;
    let lastSafeSpace = -1;

    for (let index = 0; index < remaining.length; index += 1) {
      if (remaining.startsWith('```', index)) {
        fencedCode = !fencedCode;
        index += 2;
        continue;
      }
      if (!fencedCode && remaining[index] === '`') {
        inlineCode = !inlineCode;
        continue;
      }
      if (fencedCode || inlineCode) continue;

      const char = remaining[index];
      const next = remaining[index + 1] || '';
      if (/[.!?]/.test(char) && (!next || /\s/.test(next)) && index + 1 <= MAX_SEGMENT_CHARS) {
        boundary = index + 1;
        break;
      }
      if (/[,:;]/.test(char) && index + 1 >= MIN_CLAUSE_CHARS && index + 1 <= MAX_SEGMENT_CHARS && (!next || /\s/.test(next))) {
        boundary = index + 1;
        break;
      }
      if (/\s/.test(char) && index + 1 <= MAX_SEGMENT_CHARS) lastSafeSpace = index + 1;
    }

    if (boundary < 0 && remaining.length >= MAX_SEGMENT_CHARS) {
      boundary = lastSafeSpace > 0 ? lastSafeSpace : MAX_SEGMENT_CHARS;
      // Do not split a UTF-16 surrogate pair when force-splitting a long token.
      const lastUnit = remaining.charCodeAt(boundary - 1);
      if (lastUnit >= 0xD800 && lastUnit <= 0xDBFF) boundary -= 1;
    }
    if (boundary < 0) break;

    const segment = remaining.slice(0, boundary).trim();
    if (segment) segments.push(segment);
    remaining = remaining.slice(boundary).trimStart();
  }

  if (flush && remaining.trim()) segments.push(remaining.trim());
  return { segments, remainder: flush ? '' : remaining };
}

export default function App() {
  const [status, setStatus] = useState<any>(null);
  const [hardware, setHardware] = useState<Hardware | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelTeam, setModelTeam] = useState<ModelTeamStatus | null>(null);
  const [model, setModel] = useState('qwen3.5:9b');
  const [mode, setMode] = useState<Mode>('assistant');
  const [lines, setLines] = useState<ChatLine[]>([{ role: 'assistant', content: 'Good day. I am J.A.R.V.I.S. — Just A Rather Very Idiotic System, created by Funduh (Erris). My local interface is online. How may I assist you?' }]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [coreState, setCoreState] = useState<'idle' | 'thinking' | 'learning' | 'speaking'>('idle');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [panel, setPanel] = useState<'chat' | 'memory' | 'system' | 'development'>('chat');
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryQuery, setMemoryQuery] = useState('');
  const [memoryDraft, setMemoryDraft] = useState('');
  const [memoryCategory, setMemoryCategory] = useState('general');
  const [editing, setEditing] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [listenerOn, setListenerOn] = useState(false);
  const [listenerState, setListenerState] = useState('off');
  const [voiceMode, setVoiceMode] = useState<'conversation' | 'wake'>('conversation');
  const [activityNodes, setActivityNodes] = useState<ActivityNode[]>(initialActivityNodes);
  const [selectedActivityId, setSelectedActivityId] = useState<ActivityNode['id']>('input');
  const [micTelemetry, setMicTelemetry] = useState<MicTelemetry>({ input_level: 0, input_threshold_level: 32, input_signal: false, input_dbfs: -90, queue_depth: 0, device_name: '' });
  const [lastExchange, setLastExchange] = useState<{ question: string; answer: string } | null>(null);
  const [answerExplanation, setAnswerExplanation] = useState('');
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [voiceDevices, setVoiceDevices] = useState<VoiceDevice[]>([]);
  const [voiceDevice, setVoiceDevice] = useState('default');
  const [speakReplies, setSpeakReplies] = useState(false);
  const [ttsVoice, setTtsVoice] = useState(() => { const saved = localStorage.getItem('jarvis-tts-voice'); return ['am_michael', 'am_adam', 'bm_lewis', 'bm_george'].includes(saved || '') ? saved! : 'am_michael'; });
  const [speechSpeed, setSpeechSpeed] = useState(() => { const saved = Number(localStorage.getItem('jarvis-tts-speed')); return [1, 1.08, 1.12, 1.15].includes(saved) ? saved : 1.12; });
  const [speechActive, setSpeechActive] = useState(false);
  const [styleLearning, setStyleLearning] = useState(true);
  const [styleProfile, setStyleProfile] = useState<StyleProfile | null>(null);
  const [operatorInstructions, setOperatorInstructions] = useState<OperatorInstruction[]>([]);
  const [exportingLine, setExportingLine] = useState<number | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const chatMessagesRef = useRef<HTMLDivElement | null>(null);
  const chatAutoStickRef = useRef(true);
  const speechQueueRef = useRef<string[]>([]);
  const speechAudioQueueRef = useRef<Blob[]>([]);
  const speechGeneratingRef = useRef(false);
  const speechAbortRef = useRef<AbortController | null>(null);
  const speechRunRef = useRef(0);
  const speechAudioRef = useRef<HTMLAudioElement | null>(null);
  const speechObjectUrlRef = useRef<string | null>(null);
  const speechBufferRef = useRef('');
  const speechActiveRef = useRef(false);
  const speechFinishRef = useRef<(() => void) | null>(null);
  const speechGenerationDoneRef = useRef(true);
  const speechMutedRef = useRef(false);
  const speechStatusTimerRef = useRef<number | null>(null);
  const speechPriorityPendingRef = useRef(false);
  const modelOutputStartedRef = useRef(false);
  const chatAbortRef = useRef<AbortController | null>(null);
  const pendingVoiceMessageRef = useRef<string | null>(null);
  const activitySelectionPinnedRef = useRef(false);
  const imageObjectUrlsRef = useRef<string[]>([]);
  const [fullScreen, setFullScreen] = useState(false);
  const toggleFullScreen = async () => { try { if (!document.fullscreenElement) await document.documentElement.requestFullscreen(); else await document.exitFullscreen(); } catch { setError('Full-screen mode is unavailable in this browser window.'); } };
  const createGeneratedImageObjectUrl = useCallback(async (filename: string): Promise<string> => {
    const blob = await api.generatedImage(filename);
    const objectUrl = URL.createObjectURL(blob);
    imageObjectUrlsRef.current.push(objectUrl);
    return objectUrl;
  }, []);
  useEffect(() => { const sync = () => setFullScreen(Boolean(document.fullscreenElement)); document.addEventListener('fullscreenchange', sync); return () => document.removeEventListener('fullscreenchange', sync); }, []);
  useEffect(() => () => {
    imageObjectUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    imageObjectUrlsRef.current = [];
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [s, h, m, team] = await Promise.all([
        api.status(), api.hardware(), api.models(), api.modelTeam().catch(() => null),
      ]);
      setStatus(s); setHardware(h); setModels(m.models || []); setModelTeam(team);
      if (m.models?.length && !m.models.some(item => item.name === model)) setModel(m.models[0].name);
    } catch (e) { setError(e instanceof Error ? e.message : 'Cannot reach JARVIS backend'); }
  }, [model]);
  const refreshMemories = useCallback(async () => {
    try { const result = await api.memories(memoryQuery); setMemories(result.items); }
    catch (e) { setError(e instanceof Error ? e.message : 'Memory read failed'); }
  }, [memoryQuery]);
  useEffect(() => { void refresh(); const id = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(id); }, [refresh]);
  useEffect(() => { api.voiceDevices().then(result => { setVoiceDevices(result.items || []); if (result.default_input != null) setVoiceDevice(String(result.default_input)); }).catch(() => undefined); }, []);
  useEffect(() => { api.style().then(result => { setStyleLearning(result.enabled); setStyleProfile(result.profile as StyleProfile); }).catch(() => undefined); api.operatorInstructions().then(result => setOperatorInstructions(result.items || [])).catch(() => undefined); }, []);
  useEffect(() => { localStorage.setItem('jarvis-tts-voice', ttsVoice); }, [ttsVoice]);
  useEffect(() => { localStorage.setItem('jarvis-tts-speed', String(speechSpeed)); }, [speechSpeed]);
  useEffect(() => { localStorage.setItem('jarvis-voice-mode', voiceMode); }, [voiceMode]);
  useEffect(() => { if (status?.tts_available) setSpeakReplies(true); }, [status?.tts_available]);
  useEffect(() => {
    let active = true;
    const restoreConversation = async () => {
      try {
        const result = await api.conversation(conversationId);
        if (!active || !result.messages.length) return;
        let pendingImagePrompt = '';
        const decorated = result.messages.map(message => {
          if (message.role === 'user') {
            const generatedPrompt = message.content.match(/^Generate an image:\s*([\s\S]+)$/i);
            if (generatedPrompt?.[1]) pendingImagePrompt = generatedPrompt[1].trim();
          }
          const reference = message.role === 'assistant' ? extractGeneratedImageReference(message.content) : null;
          if (!reference) return { ...message, reference: null, image_prompt: '', poster: false, design_variant: undefined };
          const imagePrompt = message.image_prompt || pendingImagePrompt;
          pendingImagePrompt = '';
          return {
            ...message, reference,
            image_prompt: imagePrompt,
            poster: message.poster ?? reference.isPoster,
            design_variant: message.design_variant || reference.designVariant || (reference.isPoster ? 'cards' : undefined),
          };
        });
        const index: { png: string[]; svg: string[] } = await api.generatedImagesIndex().catch(() => ({ png: [], svg: [] }));
        const availablePng = new Set(index.png);
        const availableSvg = new Set(index.svg);
        const restored = await Promise.all(decorated.map(async message => {
          const reference = message.reference;
          if (!reference) return { ...message, reference: undefined };
          let imageUrl: string | undefined;
          const imageExists = message.image_available !== false && availablePng.has(reference.filename);
          if (imageExists) {
            try { imageUrl = await createGeneratedImageObjectUrl(reference.filename); }
            catch { /* A file removed after the manifest check is treated as unavailable. */ }
          }
          const content = imageUrl
            ? reference.content
            : `${reference.content}${reference.content ? '\n' : ''}[This image reference has no matching PNG in the local archive. No broken preview was requested.]`;
          const svgFilename = message.poster && availableSvg.has(reference.filename.replace(/\.png$/i, '.svg'))
            ? reference.filename.replace(/\.png$/i, '.svg') : undefined;
          return {
            ...message, reference: undefined, content, imageUrl,
            imageFilename: imageExists ? reference.filename : undefined,
            imagePrompt: message.image_prompt || undefined,
            posterSourcePrompt: message.poster ? recoverPosterSourcePrompt(message.image_prompt || '') : undefined,
            isPoster: Boolean(message.poster),
            designVariant: message.design_variant,
            svgFilename,
          };
        }));
        if (active) setLines(restored);
      } catch { /* Keep the greeting visible if history is unavailable. */ }
    };
    void restoreConversation();
    return () => { active = false; };
  }, [createGeneratedImageObjectUrl]);
  useEffect(() => { if (panel === 'memory') void refreshMemories(); }, [panel, refreshMemories]);
  useEffect(() => {
    const element = chatMessagesRef.current;
    if (element && chatAutoStickRef.current) element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
  }, [lines, busy]);

  const finishSpeechIfReady = useCallback(() => {
    if (!speechGenerationDoneRef.current || speechActiveRef.current || speechGeneratingRef.current ||
        speechQueueRef.current.length || speechAudioQueueRef.current.length || speechBufferRef.current.trim()) return;
    setSpeechActive(false);
    setCoreState(current => current === 'speaking' ? 'idle' : current);
    if (listenerOn) void api.setVoiceSpeaking(false).catch(() => undefined);
    const finished = speechFinishRef.current;
    speechFinishRef.current = null;
    finished?.();
  }, [listenerOn]);

  const cancelSpeechOutput = useCallback(() => {
    speechRunRef.current += 1;
    speechPriorityPendingRef.current = false;
    if (speechStatusTimerRef.current !== null) {
      window.clearTimeout(speechStatusTimerRef.current);
      speechStatusTimerRef.current = null;
    }
    speechAbortRef.current?.abort();
    speechAbortRef.current = null;
    speechQueueRef.current = [];
    speechAudioQueueRef.current = [];
    speechBufferRef.current = '';
    const audio = speechAudioRef.current;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }
    if (speechObjectUrlRef.current) {
      URL.revokeObjectURL(speechObjectUrlRef.current);
      speechObjectUrlRef.current = null;
    }
    speechActiveRef.current = false;
    setSpeechActive(false);
    if (listenerOn) void api.setVoiceSpeaking(false).catch(() => undefined);
  }, [listenerOn]);

  const speakNext = useCallback(function pumpSpeechQueue() {
    if (speechPriorityPendingRef.current) return;
    if (speechMutedRef.current) {
      finishSpeechIfReady();
      return;
    }

    // Play already-synthesized audio immediately; synthesize the following sentence
    // in parallel with playback so the voice does not pause between every sentence.
    if (!speechActiveRef.current && speechAudioQueueRef.current.length) {
      const blob = speechAudioQueueRef.current.shift()!;
      const audio = speechAudioRef.current || new Audio();
      speechAudioRef.current = audio;
      const objectUrl = URL.createObjectURL(blob);
      speechObjectUrlRef.current = objectUrl;
      audio.src = objectUrl;
      audio.preload = 'auto';
      speechActiveRef.current = true;
      setSpeechActive(true);
      setCoreState('speaking');
      if (listenerOn) void api.setVoiceSpeaking(true).catch(() => undefined);
      let handled = false;
      const finishCurrentAudio = () => {
        if (handled) return;
        handled = true;
        audio.onended = null;
        audio.onerror = null;
        speechActiveRef.current = false;
        if (listenerOn) void api.setVoiceSpeaking(false).catch(() => undefined);
        if (speechObjectUrlRef.current === objectUrl) {
          URL.revokeObjectURL(objectUrl);
          speechObjectUrlRef.current = null;
        }
        pumpSpeechQueue();
      };
      audio.onended = finishCurrentAudio;
      audio.onerror = () => {
        setNotice('The neural voice audio could not be played. Click TEST VOICE once to enable browser audio playback.');
        speechMutedRef.current = true;
        speechQueueRef.current = [];
        speechAudioQueueRef.current = [];
        speechBufferRef.current = '';
        finishCurrentAudio();
      };
      void audio.play().catch(() => {
        setNotice('Your browser blocked audio playback. Click TEST VOICE once, then try speaking to JARVIS again.');
        speechMutedRef.current = true;
        speechQueueRef.current = [];
        speechAudioQueueRef.current = [];
        speechBufferRef.current = '';
        finishCurrentAudio();
      });
    }

    if (!speechGeneratingRef.current && speechQueueRef.current.length && speechAudioQueueRef.current.length < 1) {
      const next = speechQueueRef.current.shift()!;
      const spokenText = next
        .replace(/```[\s\S]*?```/g, 'The code is on screen.')
        .replace(/```[\s\S]*$/g, 'The code is on screen.')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
        .replace(/^\s{0,3}#{1,6}\s*/gm, '')
        .replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/gm, '')
        .replace(/[*_~>#]/g, '')
        .replace(/https?:\/\/\S+/g, 'that link')
        .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '')
        .replace(/\s+/g, ' ')
        .trim();
      if (spokenText) {
        const runId = speechRunRef.current;
        const controller = new AbortController();
        speechAbortRef.current = controller;
        speechGeneratingRef.current = true;
        setCoreState('speaking');
        void api.synthesizeSpeech(spokenText, ttsVoice, speechSpeed, controller.signal)
          .then(blob => {
            if (runId === speechRunRef.current && !speechMutedRef.current) {
              speechAudioQueueRef.current.push(blob);
            }
          })
          .catch(error => {
            if (runId === speechRunRef.current && !controller.signal.aborted) {
              speechMutedRef.current = true;
              speechQueueRef.current = [];
              speechAudioQueueRef.current = [];
              speechBufferRef.current = '';
              setNotice(error instanceof Error ? error.message : 'Local neural voice synthesis failed.');
            }
          })
          .finally(() => {
            speechGeneratingRef.current = false;
            if (speechAbortRef.current === controller) speechAbortRef.current = null;
            pumpSpeechQueue();
          });
      }
    }

    finishSpeechIfReady();
  }, [finishSpeechIfReady, listenerOn, speechSpeed, ttsVoice]);

  const enqueueStatusSpeech = useCallback(async (key: 'ack' | 'working') => {
    if (speechMutedRef.current || !speakReplies || !status?.tts_available) return;
    const runId = speechRunRef.current;
    try {
      const blob = await api.statusSpeech(key, ttsVoice, speechSpeed);
      if (runId !== speechRunRef.current || speechMutedRef.current) return;
      if (key === 'ack') speechAudioQueueRef.current.unshift(blob);
      else speechAudioQueueRef.current.push(blob);
      speakNext();
    } catch (error) {
      if (runId === speechRunRef.current && !speechMutedRef.current) {
        setNotice(error instanceof Error ? error.message : 'Could not play the local voice status update.');
      }
    }
  }, [speakNext, speakReplies, speechSpeed, status?.tts_available, ttsVoice]);

  const queueSpeech = useCallback((delta: string, flush = false) => {
    if (!speechMutedRef.current) {
      speechBufferRef.current += delta;
      // Speak at sentence boundaries, but never read the inside of code spans/fences aloud.
      const split = splitSpeechSegments(speechBufferRef.current, flush);
      speechQueueRef.current.push(...split.segments);
      speechBufferRef.current = split.remainder;
    }
    if (speechQueueRef.current.length || flush) speakNext();
  }, [speakNext]);

  const stopSpeaking = useCallback(() => {
    speechMutedRef.current = true;
    cancelSpeechOutput();
    finishSpeechIfReady();
  }, [cancelSpeechOutput, finishSpeechIfReady]);

  const previewVoice = useCallback(() => {
    if (!status?.tts_available) {
      setNotice('Install the free Kokoro neural voice first using scripts\\Install-Neural-Voice.ps1.');
      return;
    }
    cancelSpeechOutput();
    speechMutedRef.current = false;
    speechGenerationDoneRef.current = true;
    speechFinishRef.current = null;
    speechQueueRef.current.push('Good evening. Systems are online, and I am listening. How may I assist?');
    speakNext();
  }, [cancelSpeechOutput, speakNext, status?.tts_available]);

  const updateActivityNode = useCallback((activity: ActivityNode) => {
    setActivityNodes(previous => previous.map(node => node.id === activity.id ? activity : node));
    if (activity.status === 'active' && !activitySelectionPinnedRef.current) setSelectedActivityId(activity.id);
  }, []);

  const stopActiveResponse = useCallback(() => {
    pendingVoiceMessageRef.current = null;
    chatAbortRef.current?.abort();
    stopSpeaking();
    speechGenerationDoneRef.current = true;
    setSpeechActive(false);
    setCoreState('idle');
    setNotice('Stopped the current response.');
  }, [stopSpeaking]);

  const downloadCodeFiles = useCallback(async (content: string, lineIndex: number) => {
    if (!content.includes("```")) return;
    try {
      setExportingLine(lineIndex);
      const blob = await api.exportCode(content);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'jarvis-generated-files.zip';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice('Code files packaged and downloaded. A local copy is also stored under F:\\JARVIS\\generated\\exports.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not export generated code');
    } finally {
      setExportingLine(null);
    }
  }, []);

  const downloadGeneratedSvg = useCallback(async (filename: string) => {
    try {
      const blob = await api.generatedSvg(filename);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not download the SVG poster.');
    }
  }, []);

  const sendMessage = useCallback(async (rawMessage: string, speakResponse = false, fromVoice = false, imageFilenameOverride?: string) => {
    const message = rawMessage.trim();
    if (!message) return;
    if (/^(?:stop|stop it|cancel|cancel that|never mind|nevermind|be quiet)$/i.test(message)) {
      stopActiveResponse();
      return;
    }
    if (busy) {
      if (fromVoice) {
        pendingVoiceMessageRef.current = message;
        chatAbortRef.current?.abort();
        setNotice('I heard you. I am switching to your latest request.');
      } else if (speakResponse) {
        setDraft(message);
        setNotice('I caught that, but I am finishing the previous reply. Your request is in the input box.');
      }
      return;
    }

    cancelSpeechOutput();
    speechGenerationDoneRef.current = false;
    speechMutedRef.current = false;
    setSpeechActive(false);
    speechFinishRef.current = null;
    const controller = new AbortController();
    chatAbortRef.current = controller;
    if (listenerOn && voiceMode === 'wake') await api.pauseVoiceListener().catch(() => undefined);

    setError(''); setNotice('');
    setLines(prev => [...prev, { role: 'user', content: message }, { role: 'assistant', content: '' }]);
    setBusy(true);
    setCoreState(mode === 'teaching' || mode === 'interview' ? 'learning' : 'thinking');
    activitySelectionPinnedRef.current = false;
    setLastExchange(null);
    setAnswerExplanation('');
    setActivityNodes([
      { id: 'input', status: 'complete', title: 'Request received', summary: message.slice(0, 150), details: fromVoice ? 'Captured from the continuously monitored local microphone and accepted as a direct request.' : 'Submitted through the local chat interface.' },
      { id: 'memory', status: 'active', title: 'Assembling context', summary: 'Checking recent conversation and relevant saved memories.', details: `Persistent memory database currently contains ${status?.memory_count ?? 0} saved records.` },
      { id: 'model', status: 'active', title: 'Dispatching to local model team', summary: `Preparing the lead model ${model} and its independent reviewer.`, details: 'The request and relevant context are passed to the local Ollama model team. The reviewer and lead model take turns on the GPU; image and vision specialists are scheduled separately.' },
      { id: 'response', status: 'idle', title: 'Answer output', summary: 'Waiting for the model to return its first tokens.', details: 'The response will appear incrementally as Ollama generates it.' },
    ]);
    setSelectedActivityId('input');
    let completeAnswer = '';
    if (speakResponse && speakReplies) {
      speechFinishRef.current = () => {
        setSpeechActive(false);
        setCoreState('idle');
        if (listenerOn && voiceMode === 'wake') void api.resumeVoiceListener(17).catch(() => undefined);
      };
    }
    try {
      // A contextual poster request such as "create the poster now" refers to
      // the immediately preceding discussion. Do not rely on an element-only
      // keyword filter: lists of symbols, dates, or unusual subjects can be
      // dropped by that filter even though they are the actual poster content.
      const recentContextLines = lines.slice(-40);
      const relevantTopicLines = recentContextLines
        .filter(line => line.content.trim())
        .map(line => `${line.role === 'user' ? 'Operator' : 'JARVIS'}: ${line.content}`);
      const conversationContext = relevantTopicLines.join('\n').slice(-18000);
      const previousPosterLine = [...lines].reverse().find(line => line.role === 'assistant' && (line.isPoster || Boolean(line.svgFilename) || Boolean(line.imageFilename && /\b(?:poster|infographic)\b/i.test(line.imagePrompt || line.content))));
      const previousPosterDesign = previousPosterLine?.designVariant || 'cards';
      const recentPosterDesigns = lines
        .filter(line => line.role === 'assistant' && (line.isPoster || Boolean(line.svgFilename)))
        .map(line => line.designVariant)
        .filter((variant): variant is PosterDesignVariant => Boolean(variant));
      const posterRedesign = extractContextualPosterRedesignRequest(
        message,
        conversationContext,
        previousPosterLine?.posterSourcePrompt || previousPosterLine?.imagePrompt || '',
        previousPosterDesign,
        recentPosterDesigns,
      );
      const explicitPosterPrompt = extractExplicitPosterGenerationPrompt(message);
      const contextualPosterPrompt = explicitPosterPrompt || posterRedesign
        ? null
        : extractContextualImageGenerationPrompt(message, conversationContext);
      const posterPrompt = explicitPosterPrompt || posterRedesign?.prompt || contextualPosterPrompt;
      const isPosterRequest = Boolean(posterPrompt);
      const posterDesignVariant = posterRedesign?.designVariant || 'cards';
      const posterOperation = posterRedesign?.operation || 'new';
      const imagePrompt = posterPrompt || extractImageGenerationPrompt(message);
      const imageWidth = isPosterRequest ? 768 : 1024;
      const imageHeight = 1024;
      if (imagePrompt) {
        // Refresh this capability at the point of use; dashboard status can be stale.
        const imageStatus = await api.imageStatus();
        const requiredCapabilityAvailable = isPosterRequest
          ? Boolean(imageStatus.poster_available && imageStatus.runtime_installed)
          : Boolean(imageStatus.available);
        if (!requiredCapabilityAvailable) {
          const nextStep = !imageStatus.runtime_installed
            ? 'Run .\\scripts\\Install-Image-Generation.ps1 from F:\\JARVIS and approve the local dependency installation.'
            : 'Run .\\scripts\\Install-Image-Generation.ps1 from F:\\JARVIS and approve the SDXL model download.';
          throw new Error(`I recognized your image request, but the required local image capability is not ready. ${nextStep}`);
        }
        setCoreState('thinking');
        setSelectedActivityId('model');
        setActivityNodes([
          { id: 'input', status: 'complete', title: 'Image request received', summary: message.slice(0, 150), details: 'An explicit image-generation request was detected in the local interface.' },
          { id: 'memory', status: 'complete', title: 'Prompt prepared', summary: 'The requested image description is ready.', details: imagePrompt.slice(0, 900) },
          { id: 'model', status: 'active', title: isPosterRequest ? 'Structuring and typesetting poster' : 'Local SDXL generating', summary: isPosterRequest ? 'The local lead model is extracting source facts; JARVIS will typeset them as real text.' : 'Stable Diffusion XL is generating the image on the RTX GPU.', details: isPosterRequest ? 'Poster headings, labels, dates and descriptions are rendered as precise typography. SDXL is not asked to draw text.' : 'The image worker runs offline using model files stored under F:\\JARVIS\\ai\\models. Active Ollama models are unloaded temporarily to free VRAM.' },
          { id: 'response', status: 'idle', title: 'Image output', summary: 'Waiting for the PNG file to be written.', details: 'The completed image is saved to F:\\JARVIS\\generated\\images.' },
        ]);
        const initialProgress: ImageProgress = { stage: 'preparing', label: 'Preparing local image job', percent: 0, elapsedSeconds: 0, etaSeconds: null };
        setLines(previous => {
          if (!previous.length || previous[previous.length - 1].role !== 'assistant') return previous;
          const next = [...previous];
          next[next.length - 1] = { ...next[next.length - 1], imageProgress: initialProgress };
          return next;
        });
        const generated = await api.generateImageStream(
          { prompt: imagePrompt, conversation_id: conversationId, width: imageWidth, height: imageHeight, steps: 25, poster: isPosterRequest, design_variant: posterDesignVariant, poster_operation: posterOperation, previous_poster_filename: posterRedesign ? previousPosterLine?.imageFilename : undefined, poster_source_prompt: posterRedesign?.sourcePrompt, poster_design_notes: posterRedesign?.designNotes || '', poster_visual_style: posterRedesign?.visualStyle || 'default', poster_visual_density: posterRedesign?.visualDensity || 'normal', design_seed: Math.floor(Math.random() * 2147483647) },
          (event: ImageProgressEvent) => {
            if (event.type !== 'stage' && event.type !== 'progress' && event.type !== 'heartbeat') return;
            const stage = event.stage || 'working';
            const progress: ImageProgress = {
              stage,
              label: event.label || (stage === 'generating' ? 'Generating image' : stage.replace(/_/g, ' ')),
              percent: typeof event.percent === 'number' ? Math.max(0, Math.min(100, event.percent)) : null,
              step: event.step,
              totalSteps: event.total_steps,
              elapsedSeconds: event.job_elapsed_seconds ?? event.elapsed_seconds ?? 0,
              etaSeconds: event.eta_seconds ?? null,
            };
            setLines(previous => {
              if (!previous.length || previous[previous.length - 1].role !== 'assistant') return previous;
              const next = [...previous];
              next[next.length - 1] = { ...next[next.length - 1], imageProgress: progress };
              return next;
            });
            setActivityNodes(previous => previous.map(node => node.id === 'model'
              ? { ...node, status: 'active', title: progress.label, summary: progress.percent == null ? progress.label : `${Math.round(progress.percent)}% · ${progress.step ?? 0}/${progress.totalSteps ?? 25} steps`, details: `Elapsed ${formatDuration(progress.elapsedSeconds)} · ${formatDuration(progress.etaSeconds)} remaining. ${isPosterRequest ? 'Poster layout and typography are rendered locally.' : 'Progress is reported by the SDXL worker, not simulated.'}` }
              : node));
          },
          controller.signal,
        );
        completeAnswer = isPosterRequest
          ? (posterOperation === 'refine'
            ? `I refined the existing poster using your direction: ${posterRedesign?.designNotes || 'visual improvements'}. The updated poster was saved as a new file.`
            : `I created a fresh poster composition (${posterDesignVariant}) while preserving the original educational content. The new PNG and SVG were saved.`)
          : 'Here it is. Created locally with Stable Diffusion XL.';
        let generatedImageUrl: string | undefined;
        try {
          // Fetch the PNG through the authenticated same-origin API, then render a blob URL.
          // This avoids relying on the browser's <img> request to carry the local API token.
          generatedImageUrl = await createGeneratedImageObjectUrl(generated.filename);
        } catch (imageLoadError) {
          const detail = imageLoadError instanceof Error ? imageLoadError.message : 'Unknown preview error';
          completeAnswer += `\nThe PNG was saved, but the chat preview could not be loaded: ${detail}\nFile: F:\\JARVIS\\generated\\images\\${generated.filename}`;
        }
        setLines(prev => {
          if (!prev.length || prev[prev.length - 1].role !== 'assistant') return prev;
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', content: completeAnswer, imageUrl: generatedImageUrl, imageFilename: generated.filename, svgFilename: generated.svg_filename || undefined, imagePrompt, posterSourcePrompt: isPosterRequest ? (posterRedesign?.sourcePrompt || posterPrompt || imagePrompt) : undefined, isPoster: isPosterRequest, designVariant: isPosterRequest ? posterDesignVariant : undefined, imageProgress: { stage: 'complete', label: 'Image ready', percent: 100, step: generated.step ?? (isPosterRequest ? 1 : 25), totalSteps: generated.total_steps ?? (isPosterRequest ? 1 : 25), elapsedSeconds: generated.elapsed_seconds ?? 0, etaSeconds: 0 } };
          return next;
        });
        setLastExchange({ question: message, answer: completeAnswer });
        setAnswerExplanation('');
        setActivityNodes(previous => previous.map(node => node.id === 'model'
          ? { ...node, status: 'complete', title: isPosterRequest ? 'Poster typeset' : 'Image generated', summary: isPosterRequest ? 'All poster copy was rendered as crisp text.' : 'SDXL completed the image on the local GPU.', details: `Prompt: ${imagePrompt}` }
          : node.id === 'response'
            ? { ...node, status: 'complete', title: 'Image saved', summary: 'The generated PNG is now displayed in the conversation.', details: `Saved under F:\\JARVIS\\generated\\images\\${generated.filename}` }
            : node));
        speechGenerationDoneRef.current = true;
        if (speakResponse && speakReplies) queueSpeech(isPosterRequest ? 'Here is the readable poster.' : 'Here it is. I created that locally.', true);
        else setCoreState('idle');
        await refresh();
        return;
      }

      const latestImageFilename = imageFilenameOverride || [...lines].reverse().find(line => line.role === 'assistant' && line.imageFilename)?.imageFilename;
      if (latestImageFilename && (imageFilenameOverride || isGeneratedImageFollowUp(message))) {
        setSelectedActivityId('model');
        setActivityNodes([
          { id: 'input', status: 'complete', title: 'Image question received', summary: message.slice(0, 150), details: 'The request references a previously generated JARVIS image.' },
          { id: 'memory', status: 'complete', title: 'Image loaded', summary: 'The exact saved PNG is attached to the local vision request.', details: `Image file: ${latestImageFilename}` },
          { id: 'model', status: 'active', title: 'Local vision model', summary: 'Passing the PNG to the configured Ollama vision-language model.', details: 'The image is read from F:\\JARVIS\\generated\\images and sent only to the local Ollama service.' },
          { id: 'response', status: 'idle', title: 'Visual analysis', summary: 'Waiting for the local vision model.', details: 'JARVIS will describe only what the model can actually inspect in the attached image.' },
        ]);
        const analyzed = await api.analyzeGeneratedImage({ filename: latestImageFilename, question: message, conversation_id: conversationId });
        completeAnswer = analyzed.answer;
        setLines(previous => {
          if (!previous.length || previous[previous.length - 1].role !== 'assistant') return previous;
          const next = [...previous];
          next[next.length - 1] = { role: 'assistant', content: completeAnswer };
          return next;
        });
        setLastExchange({ question: message, answer: completeAnswer });
        setAnswerExplanation('');
        setActivityNodes(previous => previous.map(node => ({ ...node, status: 'complete', summary: node.id === 'model' ? `Visual analysis completed with ${analyzed.model}.` : node.summary })));
        speechGenerationDoneRef.current = true;
        if (speakResponse && speakReplies) queueSpeech(completeAnswer, true);
        else setCoreState('idle');
        await refresh();
        return;
      }

      modelOutputStartedRef.current = false;
      const narrateProgress = speakResponse && speakReplies && status?.tts_available && shouldUseProgressSpeech(message);
      if (narrateProgress) {
        const progressRunId = speechRunRef.current;
        speechPriorityPendingRef.current = true;
        void enqueueStatusSpeech('ack').finally(() => {
          if (progressRunId === speechRunRef.current) {
            speechPriorityPendingRef.current = false;
            speakNext();
          }
        });
        speechStatusTimerRef.current = window.setTimeout(() => {
          speechStatusTimerRef.current = null;
          if (!modelOutputStartedRef.current && !speechGenerationDoneRef.current && !speechMutedRef.current) {
            void enqueueStatusSpeech('working');
          }
        }, 3600);
      }
      const result = await api.chatStream(
        { message, conversation_id: conversationId, mode, model, voice_mode: speakResponse && speakReplies },
        delta => {
          if (delta && !modelOutputStartedRef.current) {
            modelOutputStartedRef.current = true;
            if (speechStatusTimerRef.current !== null) {
              window.clearTimeout(speechStatusTimerRef.current);
              speechStatusTimerRef.current = null;
            }
          }
          completeAnswer += delta;
          setLines(prev => {
            if (!prev.length || prev[prev.length - 1].role !== 'assistant') return prev;
            const next = [...prev];
            next[next.length - 1] = { role: 'assistant', content: completeAnswer };
            return next;
          });
          if (speakResponse && speakReplies) queueSpeech(delta);
        },
        updateActivityNode,
        controller.signal,
      );
      const imageReference = extractGeneratedImageReference(result.answer);
      let answerForDisplay = imageReference?.content ?? result.answer;
      let inlineImageUrl: string | undefined;
      if (imageReference) {
        const index = await api.generatedImagesIndex().catch(() => ({ png: [], svg: [] }));
        if (index.png.includes(imageReference.filename)) {
          try { inlineImageUrl = await createGeneratedImageObjectUrl(imageReference.filename); }
          catch { /* The preview is omitted if the file disappears after the manifest check. */ }
        }
        if (!inlineImageUrl) {
          answerForDisplay = 'The text model returned an unverified image reference, but no corresponding image file exists. No image was generated by the image service.';
        }
      } else if (isUnverifiedImageCreationClaim(result.answer)) {
        answerForDisplay = 'I did not run the local image-generation service for that reply, so no new image was created or saved. I will only report an image as generated after the image worker returns a verified PNG file.';
      }
      completeAnswer = answerForDisplay;
      setLastExchange({ question: message, answer: answerForDisplay });
      setAnswerExplanation('');
      if (!activitySelectionPinnedRef.current) setSelectedActivityId('model');
      setLines(prev => {
        if (!prev.length || prev[prev.length - 1].role !== 'assistant') return prev;
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: answerForDisplay, imageUrl: inlineImageUrl, imageFilename: inlineImageUrl ? imageReference?.filename : undefined, isPoster: inlineImageUrl ? imageReference?.isPoster : undefined, designVariant: inlineImageUrl ? imageReference?.designVariant : undefined };
        return next;
      });
      if (result.memory_notice) setNotice(result.memory_notice);
      if (result.incomplete) setNotice('The model reached its output limit after continuation. The answer may still be incomplete; ask JARVIS to continue from the final line.');
      speechGenerationDoneRef.current = true;
      if (speechStatusTimerRef.current !== null) {
        window.clearTimeout(speechStatusTimerRef.current);
        speechStatusTimerRef.current = null;
      }
      if (speakResponse && speakReplies) queueSpeech('', true);
      else {
        setCoreState('idle');
        if (listenerOn && voiceMode === 'wake') void api.resumeVoiceListener(0).catch(() => undefined);
      }
      await refresh();
      const style = await api.style().catch(() => null);
      if (style) setStyleProfile(style.profile as StyleProfile);
      const instructions = await api.operatorInstructions().catch(() => null);
      if (instructions) setOperatorInstructions(instructions.items || []);
    } catch (e) {
      speechGenerationDoneRef.current = true;
      if (speechStatusTimerRef.current !== null) {
        window.clearTimeout(speechStatusTimerRef.current);
        speechStatusTimerRef.current = null;
      }
      const aborted = e instanceof DOMException && e.name === 'AbortError';
      if (!aborted) {
        const failureMessage = e instanceof Error ? e.message : 'Chat request failed';
        setError(failureMessage);
        setLines(previous => {
          if (!previous.length || previous[previous.length - 1].role !== 'assistant' || !previous[previous.length - 1].imageProgress) return previous;
          const next = [...previous];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: 'Image generation failed. See the error details above.', imageProgress: { ...last.imageProgress!, stage: 'error', label: 'Generation failed', etaSeconds: null } };
          return next;
        });
      }
      if (speechQueueRef.current.length || speechAudioQueueRef.current.length || speechActiveRef.current || speechGeneratingRef.current) stopSpeaking();
      else {
        speechFinishRef.current = null;
        if (listenerOn && voiceMode === 'wake') void api.resumeVoiceListener(0).catch(() => undefined);
      }
      setCoreState('idle');
      if (aborted) {
        setActivityNodes(previous => previous.map(node => node.id === 'response' ? { ...node, status: 'warning', title: 'Request interrupted', summary: 'The active request was cancelled.', details: 'The frontend stopped waiting and the backend terminates an active SDXL worker when its stream is cancelled.' } : node));
        setLines(previous => {
          if (!previous.length || previous[previous.length - 1].role !== 'assistant' || !previous[previous.length - 1].imageProgress) return previous;
          const next = [...previous];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: 'Image generation cancelled.', imageProgress: { ...last.imageProgress!, stage: 'cancelled', label: 'Generation cancelled', etaSeconds: null } };
          return next;
        });
      }
    } finally {
      if (chatAbortRef.current === controller) chatAbortRef.current = null;
      setBusy(false);
    }
  }, [busy, cancelSpeechOutput, createGeneratedImageObjectUrl, enqueueStatusSpeech, lines, listenerOn, mode, model, queueSpeech, refresh, speakNext, speakReplies, status?.memory_count, status?.tts_available, stopActiveResponse, stopSpeaking, updateActivityNode, voiceMode]);

  useEffect(() => {
    if (busy || !pendingVoiceMessageRef.current) return;
    const nextMessage = pendingVoiceMessageRef.current;
    pendingVoiceMessageRef.current = null;
    void sendMessage(nextMessage, speakReplies, true);
  }, [busy, sendMessage, speakReplies]);


  const send = async () => {
    const message = draft.trim();
    if (!message) return;
    if (/^(?:stop|stop it|cancel|cancel that|never mind|nevermind|be quiet)$/i.test(message)) {
      setDraft('');
      stopActiveResponse();
      return;
    }
    if (busy) return;
    setDraft('');
    await sendMessage(message, speakReplies);
  };

  const startConversationListener = async () => {
    try {
      setError('');
      setNotice(voiceMode === 'conversation' ? 'Starting continuous local conversation listening…' : 'Starting the local Hey JARVIS detector…');
      const deviceIndex = voiceDevice === 'default' ? null : Number(voiceDevice);
      const result = await api.startVoiceListener(deviceIndex, voiceMode);
      setListenerOn(true); setListenerState(result.state || 'starting');
      setNotice(voiceMode === 'conversation'
        ? 'Conversation Mode is active. JARVIS listens continuously and responds to detected direct questions or commands; no wake phrase is required.'
        : 'Wake-word mode is active. Say “Hey JARVIS”, pause briefly, then speak your request.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not enable voice conversation'); setNotice(''); }
  };

  const toggleStyleLearning = async () => {
    const next = !styleLearning;
    try {
      const result = await api.updateStyle(next);
      setStyleLearning(result.enabled);
      setStyleProfile(result.profile as StyleProfile);
      setNotice(next
        ? 'Style learning enabled. JARVIS will adapt from aggregate patterns in your messages; raw examples are not added to the style profile.'
        : 'Style learning paused. Your existing style profile is retained locally but will not be updated or applied.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update style learning'); }
  };

  const stopWakeListener = async () => {
    try {
      const result = await api.stopVoiceListener();
      setListenerOn(false); setListenerState(result.state || 'off');
      setMicTelemetry({ input_level: 0, input_threshold_level: 32, input_signal: false, input_dbfs: -90, queue_depth: 0, device_name: '' });
      setNotice('Conversation listening is off. The microphone has been released.');
      chatAbortRef.current?.abort();
      speechMutedRef.current = true;
      cancelSpeechOutput();
      speechFinishRef.current = null;
      setCoreState('idle');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not stop wake-word listening'); }
  };

  useEffect(() => {
    if (!listenerOn) return;
    let polling = false;
    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const result = await api.voiceEvents();
        setListenerState(result.listener?.state || 'listening');
        for (const event of result.events as VoiceEvent[]) {
          if (event.type === 'wake') {
            setListenerState('activated'); setNotice('JARVIS heard the wake phrase. Listening…');
          } else if (event.type === 'followup') {
            setListenerState('activated'); setNotice('I am listening. Go ahead.');
          } else if (event.type === 'ignored') {
            // Nearby conversation is intentionally ignored quietly to avoid interrupting the user.
          } else if (event.type === 'barge_in') {
            setNotice('I heard you. Go ahead.');
            stopSpeaking();
            chatAbortRef.current?.abort();
          } else if (event.type === 'command' && event.text) {
            setListenerState('processing'); setNotice(`Voice request recognized${event.language ? ` (${event.language})` : ''}.`);
            void sendMessage(event.text, speakReplies, true);
          } else if (event.type === 'empty') {
            setNotice(event.message || 'I heard you call me.');
            await api.pauseVoiceListener();
            speechFinishRef.current = () => { void api.voiceStatus().then(state => state.enabled ? api.resumeVoiceListener(17) : undefined).catch(() => undefined); };
            queueSpeech('Yes, Funduh?', true);
          } else if (event.type === 'error') {
            setError(event.message || 'Wake-word voice processing failed.'); setNotice('');
          } else if (event.type === 'state' && event.state === 'error') {
            setError(event.error || 'Wake-word listener stopped unexpectedly.'); setNotice(''); setListenerOn(false);
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Lost connection to the voice listener.');
        setListenerOn(false);
      } finally { polling = false; }
    };
    const timer = window.setInterval(() => void poll(), 150);
    void poll();
    return () => window.clearInterval(timer);
  }, [listenerOn, sendMessage, queueSpeech, speakReplies, stopSpeaking]);
  const addMemory = async () => {
    if (!memoryDraft.trim()) return;
    try { await api.addMemory({ content: memoryDraft.trim(), category: memoryCategory, tags: '' }); setMemoryDraft(''); await refreshMemories(); await refresh(); setNotice('Memory saved to the local SQLite database. This does not train model weights.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save memory'); }
  };
  const saveEdit = async (item: Memory) => {
    if (!editContent.trim()) return;
    try { await api.updateMemory(item.id, { content: editContent.trim(), category: item.category, tags: item.tags }); setEditing(null); await refreshMemories(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not update memory'); }
  };
  const removeMemory = async (id: number) => {
    if (!window.confirm('Permanently delete this memory from the local database?')) return;
    try { await api.deleteMemory(id); await refreshMemories(); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not delete memory'); }
  };

  const explainLastAnswer = async () => {
    if (!lastExchange || explanationLoading) return;
    try {
      setExplanationLoading(true);
      setAnswerExplanation('');
      setSelectedActivityId('model');
      setActivityNodes(previous => previous.map(node => node.id === 'model' ? { ...node, status: 'active', title: 'Reviewing answer basis', summary: `Asking ${model} for a concise explanation using the original request and supplied context.`, details: 'This optional second local inference summarizes the answer basis and assumptions. It does not expose private token-by-token reasoning.' } : node));
      const result = await api.explainAnswer({
        question: lastExchange.question,
        answer: lastExchange.answer,
        conversation_id: conversationId,
        model,
      });
      setAnswerExplanation(result.explanation);
      setActivityNodes(previous => previous.map(node => node.id === 'model' ? {
        ...node,
        status: 'complete',
        title: 'Answer basis explained',
        summary: `A local explanation was generated by ${model}; ${result.memory_excerpts_supplied} relevant saved-memory excerpt(s) were supplied as context.`,
        details: 'The explanation summarizes the interpreted request, visible basis, high-level justification and uncertainty. It is an explanation of the answer, not a transcript of hidden model reasoning.',
      } : node));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not explain the previous answer.');
    } finally {
      setExplanationLoading(false);
    }
  };

  const stopMicrophoneTracks = () => {
    mediaStreamRef.current?.getTracks().forEach(track => track.stop());
    mediaStreamRef.current = null;
  };
  const startVoiceRecording = async () => {
    if (!status?.voice_available) {
      setError('Local voice recognition is not installed yet. Run scripts\\Install-Voice-Model.ps1 from the F:\\JARVIS project root.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('This browser does not support microphone recording. Try the latest Chrome or Edge on localhost.');
      return;
    }
    try {
      setError(''); setNotice('');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      mediaStreamRef.current = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = event => { if (event.data.size) audioChunksRef.current.push(event.data); };
      recorder.onerror = () => { setError('Microphone recording failed. Check the microphone and browser permissions.'); setRecording(false); stopMicrophoneTracks(); };
      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        stopMicrophoneTracks();
        if (!blob.size) { setError('No audio was captured. Please try again.'); return; }
        setTranscribing(true); setError(''); setNotice('Transcribing locally on this PC…');
        try {
          const result = await api.transcribe(blob);
          setDraft(current => current ? `${current.trim()} ${result.text}` : result.text);
          setNotice(`Voice transcription ready${result.language ? ` (detected: ${result.language})` : ''}. Review the text, then press Send.`);
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Local voice transcription failed.');
          setNotice('');
        } finally { setTranscribing(false); }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setNotice('Microphone is active. Press the microphone button again to stop and transcribe.');
    } catch (e) {
      stopMicrophoneTracks();
      setError(e instanceof Error ? e.message : 'Microphone permission was denied or unavailable.');
    }
  };
  const stopVoiceRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    setRecording(false);
  };
  useEffect(() => () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    stopMicrophoneTracks();
  }, []);
  useEffect(() => () => { if (listenerOn) void api.stopVoiceListener().catch(() => undefined); speechMutedRef.current = true; cancelSpeechOutput(); }, [listenerOn, cancelSpeechOutput]);

  const gpu = hardware?.gpu;
  const modelAvailable = Boolean(status?.installed_models?.includes(model));
  const greetingTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return <main className={fullScreen ? 'app-shell fullscreen' : 'app-shell'}>
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Orbit size={21} /></div><div><div className="brand-title">J.A.R.V.I.S.</div><div className="brand-sub">JUST A RATHER VERY IDIOTIC SYSTEM</div><div className="creator-line">CREATED BY FUNDUH / ERRIS</div></div></div>
      <div className="top-status"><span className={`status-dot ${status?.ollama_available ? 'online' : 'offline'}`} />{status?.ollama_available ? 'LOCAL BRAIN CONNECTED' : 'LOCAL BRAIN OFFLINE'}<span className="separator">/</span><span>LOCAL MODE</span></div>
      <div className="top-actions"><span className="clock">{greetingTime}</span><button className="icon-btn" title="Refresh telemetry" onClick={() => void refresh()}><RefreshCw size={16}/></button><button className="icon-btn" title="Toggle full screen layout" onClick={() => void toggleFullScreen()}>{fullScreen ? <X size={16}/> : <ChevronDown size={16}/>}</button></div>
    </header>
    <section className="dashboard-grid">
      <aside className="left-rail panel">
        <div className="panel-heading"><span>CORE SYSTEM</span><span className="tiny-code">SYS.01</span></div>
        <div className="core-status"><div className="live-line"><span className="status-dot online"/> {busy ? 'PROCESSING REQUEST' : 'STANDBY'}</div><div className="core-name">JARVIS CORE</div><div className="muted small">Local inference coordinator</div></div>
        <div className="metric-block"><div className="metric-label"><Cpu size={14}/> PROCESSOR <b>{fmt(hardware?.cpu_percent, '%')}</b></div><div className="meter"><i style={{ width: `${hardware?.cpu_percent || 0}%` }}/></div></div>
        <div className="metric-block"><div className="metric-label"><Database size={14}/> SYSTEM RAM <b>{hardware ? `${fmt(hardware.ram_used_gb)} / ${fmt(hardware.ram_total_gb)} GB` : '—'}</b></div><div className="meter"><i style={{ width: `${hardware?.ram_percent || 0}%` }}/></div></div>
        <div className="metric-block"><div className="metric-label"><Activity size={14}/> GPU LOAD <b>{fmt(gpu?.utilization_percent, '%')}</b></div><div className="meter"><i style={{ width: `${gpu?.utilization_percent || 0}%` }}/></div></div>
        <div className="metric-block"><div className="metric-label"><HardDrive size={14}/> GPU MEMORY <b>{gpu?.available ? `${fmt((gpu.vram_used_mb || 0) / 1024)} / ${fmt((gpu.vram_total_mb || 0) / 1024)} GB` : 'N/A'}</b></div><div className="meter"><i style={{ width: `${gpu?.available && gpu.vram_total_mb ? (gpu.vram_used_mb || 0) / gpu.vram_total_mb * 100 : 0}%` }}/></div></div>
        <div className="mini-grid"><div><span className="muted">GPU TEMP</span><b>{fmt(gpu?.temperature_c, '°C')}</b></div><div><span className="muted">GPU POWER</span><b>{fmt(gpu?.power_w, ' W')}</b></div></div>
        <div className="panel-footer"><ShieldCheck size={14}/> Filesystem boundary: imports only</div>
      </aside>

      <section className="center-stage panel">
        <div className="stage-head"><div><div className="eyebrow">NEURAL INTERFACE / 001</div><h1>HOLOGRAPHIC CORE</h1></div><div className="stage-state"><span className={`state-pip ${coreState}`}/>{coreState.toUpperCase()}</div></div>
        <div className="holo-wrap"><div className="holo-orbit orbit-a"/><div className="holo-orbit orbit-b"/><Hologram state={coreState} knowledgeCount={status?.memory_count ?? 0} activity={activityNodes} selectedNodeId={selectedActivityId} onNodeSelect={id => { activitySelectionPinnedRef.current = true; setSelectedActivityId(id); }}/><div className="holo-caption"><span>J.A.R.V.I.S. // LOCAL INSTANCE</span><span>KNOWLEDGE CORE · {status?.memory_count ?? 0} STORED NODES</span></div></div>
        <div className="activity-inspector">
          <div className="activity-inspector-head"><span>LIVE DECISION TRACE</span><span>SELECT A NODE</span></div>
          {(() => { const selected = activityNodes.find(node => node.id === selectedActivityId) || activityNodes[0]; return <div className="activity-inspector-body"><b>{selected.title}</b><span className={`activity-state ${selected.status}`}>{selected.status.toUpperCase()}</span><p>{selected.summary}</p><small>{selected.details}</small></div>; })()}
          {lastExchange && <button className="explain-answer-btn" onClick={() => void explainLastAnswer()} disabled={explanationLoading}>
            {explanationLoading ? <><LoaderCircle size={12} className="spin"/> BUILDING ANSWER EXPLANATION…</> : <><Brain size={12}/> HOW DID I REACH THIS ANSWER?</>}
          </button>}
          {answerExplanation && <div className="answer-explanation"><div className="answer-explanation-title">USER-FACING REASONING SUMMARY</div><p>{answerExplanation}</p></div>}
          <div className="activity-disclaimer">Click a node to inspect its real inputs and processing. Request an answer-basis summary when you want the justification.</div>
        </div>
        <div className="quick-stats"><div><span>MODEL</span><b>{model}</b></div><div><span>MEMORY NODES</span><b>{status?.memory_count ?? 0}</b></div><div><span>INFERENCE</span><b>{status?.ollama_available && modelAvailable ? 'READY' : 'NOT READY'}</b></div><div><span>NETWORK</span><b>LOOPBACK ONLY</b></div></div>
      </section>

      <aside className="right-rail panel">
        <div className="tab-row"><button className={panel === 'chat' ? 'tab active' : 'tab'} onClick={() => setPanel('chat')}><MessageSquare size={14}/> ASSISTANT</button><button className={panel === 'memory' ? 'tab active' : 'tab'} onClick={() => setPanel('memory')}><Brain size={14}/> MEMORY</button><button className={panel === 'development' ? 'tab active' : 'tab'} onClick={() => setPanel('development')}><Code2 size={14}/> SELF DEV</button><button className={panel === 'system' ? 'tab active' : 'tab'} onClick={() => setPanel('system')}><Activity size={14}/> SYSTEM</button></div>
        {panel === 'chat' && <div className="chat-panel">
          <div className="chat-toolbar"><div><div className="eyebrow">CONVERSATIONAL INTERFACE</div><div className="chat-title">Talk to JARVIS</div></div><select value={mode} onChange={e => setMode(e.target.value as Mode)} aria-label="Learning mode">{modes.map(m => <option key={m.id} value={m.id}>{m.label} mode</option>)}</select></div>
          <div className="wake-controls">
            <select aria-label="Microphone input" value={voiceDevice} onChange={e => setVoiceDevice(e.target.value)} disabled={listenerOn}>
              <option value="default">System default microphone</option>
              {voiceDevices.map(device => <option key={device.index} value={String(device.index)}>{device.name}{device.default ? ' (default)' : ''}</option>)}
            </select>
            <select className="voice-mode-select" aria-label="Voice conversation mode" value={voiceMode} onChange={e => setVoiceMode(e.target.value as 'conversation' | 'wake')} disabled={listenerOn} title="Choose always-listening conversation or wake-word-only mode"><option value="conversation">CONVERSATION · NO WAKE PHRASE</option><option value="wake">WAKE WORD · HEY JARVIS</option></select>
            <div className={`mic-input-meter ${listenerOn ? 'enabled' : ''}`} aria-label={`Microphone input level ${Math.round(micTelemetry.input_level)} percent`}>
              <div className="mic-input-heading"><span><Mic size={11}/> LIVE MIC LEVEL</span><b>{listenerOn ? `${Math.round(micTelemetry.input_level)}%` : 'MIC OFF'}</b></div>
              <div className="mic-input-track" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(micTelemetry.input_level)}>
                <i style={{ width: `${Math.max(0, Math.min(100, micTelemetry.input_level))}%` }}/>
                {voiceMode === 'conversation' && <em style={{ left: `${Math.max(0, Math.min(100, micTelemetry.input_threshold_level))}%` }}/>}
              </div>
              <small>{!listenerOn ? 'START CONVERSATION TO CHECK INPUT' : `${micTelemetry.device_name || 'INPUT ACTIVE'} · ${voiceMode === 'wake' ? 'WAKE DETECTOR ACTIVE' : micTelemetry.input_signal ? 'AUDIO ABOVE VOICE GATE' : 'LISTENING'} · ${micTelemetry.queue_depth} QUEUED`}</small>
            </div>
            <button className={listenerOn ? 'wake-btn active' : 'wake-btn'} onClick={() => listenerOn ? void stopWakeListener() : void startConversationListener()} disabled={!listenerOn && (!status?.voice_available || (voiceMode === 'wake' && !status?.wake_word_available))} title="Start or stop local voice conversation">{listenerOn ? <><MicOff size={13}/> CONVERSATION ON · {listenerState.toUpperCase()}</> : <><Mic size={13}/> START CONVERSATION</>}</button>
            <select className="tts-voice-select" aria-label="JARVIS neural voice" value={ttsVoice} onChange={e => setTtsVoice(e.target.value)} disabled={!status?.tts_available} title="Choose JARVIS's local neural voice"><option value="am_michael">MICHAEL · CLEAR US</option><option value="am_adam">ADAM · US MALE</option><option value="bm_lewis">LEWIS · BRITISH</option><option value="bm_george">GEORGE · BRITISH</option></select>
            <select className="tts-voice-select tts-speed-select" aria-label="Speech speed" value={String(speechSpeed)} onChange={e => setSpeechSpeed(Number(e.target.value))} disabled={!status?.tts_available} title="Adjust JARVIS's speaking speed"><option value="1">1.00× NATURAL</option><option value="1.08">1.08× BRISK</option><option value="1.12">1.12× FAST</option><option value="1.15">1.15× VERY FAST</option></select>
            <label className="speak-toggle"><input type="checkbox" checked={speakReplies} disabled={!status?.tts_available} onChange={e => { setSpeakReplies(e.target.checked); if (!e.target.checked) stopSpeaking(); }}/> SPEAK REPLIES</label>
            <button className="test-voice-btn" onClick={previewVoice} disabled={!status?.tts_available || speechActive || busy}>TEST VOICE</button>
            {!status?.tts_available && <span className="tts-unavailable">INSTALL KOKORO VOICE</span>}
            <label className="speak-toggle style-toggle" title="Learn aggregate patterns from your messages; raw examples are not added to the style profile."><input type="checkbox" checked={styleLearning} onChange={() => void toggleStyleLearning()}/> LEARN MY STYLE{styleProfile?.samples ? ` · ${styleProfile.samples}` : ''}</label>
            {speechActive && <button className="stop-speech-btn" onClick={stopSpeaking}>STOP TALKING</button>}
          </div>
          <div className="model-select"><label>TEAM PRIMARY</label><select value={model} onChange={e => setModel(e.target.value)}>{models.length ? models.map(m => <option key={m.name} value={m.name}>{m.name}</option>) : <option value={model}>{model} (not detected)</option>}</select></div>
          <div className="model-team-status" aria-live="polite">
            <span>LOCAL MODEL TEAM</span>
            {modelTeam?.available ? <div>
              <b>LEAD</b> {modelTeam.primary || model}
              <b>REVIEW</b> {modelTeam.reviewer || 'single-model fallback'}
              <b>VISION</b> {modelTeam.vision_specialist || 'not available'}
              <b>IMAGE</b> {modelTeam.image_generator || 'not available'}
            </div> : <div>Model-team status unavailable · chat will use the backend's local fallback.</div>}
          </div>
          <div className="chat-messages" ref={chatMessagesRef} onScroll={e => { const el = e.currentTarget; chatAutoStickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>{lines.map((line, i) => <div className={`chat-line ${line.role}`} key={i}><div className="line-avatar">{line.role === 'assistant' ? <Sparkles size={13}/> : 'YOU'}</div><div className="line-content"><div className="line-label">{line.role === 'assistant' ? 'J.A.R.V.I.S.' : 'OPERATOR'}</div><div className="line-text">{line.content}</div>{line.imageProgress && <div className="image-progress-card"><div className="image-progress-heading"><b>{line.imageProgress.label.toUpperCase()}</b><span>{line.imageProgress.percent == null ? '—' : `${Math.round(line.imageProgress.percent)}%`}</span></div><div className="image-progress-track"><span style={{ width: `${line.imageProgress.percent ?? 0}%` }}/></div><div className="image-progress-meta"><span>{line.imageProgress.step != null && line.imageProgress.totalSteps != null ? `STEP ${line.imageProgress.step} / ${line.imageProgress.totalSteps}` : line.imageProgress.stage.replace(/_/g, ' ').toUpperCase()}</span><span>ELAPSED {formatDuration(line.imageProgress.elapsedSeconds)}</span><span>{line.imageProgress.stage === 'complete' ? 'COMPLETE' : line.imageProgress.stage === 'cancelled' ? 'CANCELLED' : line.imageProgress.stage === 'saving' ? 'FINALIZING' : line.imageProgress.stage === 'error' ? 'FAILED' : line.imageProgress.etaSeconds == null ? 'ETA CALCULATING' : `ETA ${formatDuration(line.imageProgress.etaSeconds)}`}</span></div></div>}{line.imageUrl && <div className="generated-image-wrap"><a className="generated-image-link" href={line.imageUrl} target="_blank" rel="noreferrer"><img className="generated-image" src={line.imageUrl} alt="Image generated locally by JARVIS"/></a><div className="generated-image-actions"><a href={line.imageUrl} download="jarvis-generated-image.png">DOWNLOAD IMAGE</a>{line.svgFilename && <button onClick={() => void downloadGeneratedSvg(line.svgFilename!)}>DOWNLOAD SVG</button>}{line.imageFilename && <button onClick={() => void sendMessage('Describe this image and tell me whether it matches what I asked for.', false, false, line.imageFilename)} disabled={busy}>ASK JARVIS ABOUT THIS IMAGE</button>}</div></div>}{!line.imageUrl && line.imageFilename && <div className="generated-image-actions"><button onClick={() => void sendMessage('Describe this image and tell me whether it matches what I asked for.', false, false, line.imageFilename)} disabled={busy}>ASK JARVIS ABOUT THIS IMAGE</button></div>}{line.role === 'assistant' && line.content.includes('```') && <button className="export-code-btn" onClick={() => void downloadCodeFiles(line.content, i)} disabled={busy || exportingLine === i}><Download size={13}/>{exportingLine === i ? 'PACKAGING…' : 'DOWNLOAD CODE FILES'}</button>}</div></div>)}</div>
          {error && <div className="inline-error">{error}</div>}{notice && <div className="inline-notice">{notice}</div>}
          <div className="composer"><textarea value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); } }} placeholder="Enter a message… (Enter to send)" rows={2}/><button className={recording ? 'mic-btn recording' : 'mic-btn'} onClick={() => recording ? stopVoiceRecording() : void startVoiceRecording()} disabled={listenerOn || busy || transcribing || (!status?.voice_available && !recording)} title={recording ? 'Stop microphone and transcribe' : status?.voice_available ? 'Start local voice recording' : 'Install local voice recognition first'}>{transcribing ? <LoaderCircle size={16} className="spin"/> : recording ? <MicOff size={16}/> : <Mic size={16}/>}</button>{busy && <button className="stop-generation-btn" onClick={stopActiveResponse} title="Stop the current response"><StopCircle size={16}/></button>}<button onClick={() => void send()} disabled={busy || !draft.trim()} className="send-btn"><Send size={16}/></button></div>
          <div className="chat-foot"><span><span className="status-dot online"/> LOCAL PROCESSING ONLY</span><span>{listenerOn ? `${voiceMode === 'conversation' ? 'CONTINUOUS CONVERSATION' : 'WAKE WORD LISTENER'} · ${listenerState.toUpperCase()}` : recording ? 'MICROPHONE ACTIVE · CLICK TO STOP' : transcribing ? 'LOCAL TRANSCRIPTION IN PROGRESS' : status?.voice_available ? 'LOCAL VOICE INPUT READY · DISABLED' : 'VOICE MODEL NOT INSTALLED'} · {status?.tts_available ? 'KOKORO NEURAL TTS' : 'NEURAL VOICE NOT INSTALLED'}</span></div>
        </div>}
        {panel === 'memory' && <div className="memory-panel">
          <div className="chat-toolbar"><div><div className="eyebrow">PERSISTENT KNOWLEDGE STORE</div><div className="chat-title">Memory management</div></div><span className="memory-count">{memories.length} / {status?.memory_count ?? 0}</span></div>
          <p className="muted small">Saved locally in SQLite. Memory retrieval is keyword-based in this build, not vector search. Saving memory does not train the model.</p>
          {operatorInstructions.length > 0 && <section className="operator-instruction-list"><div className="operator-instruction-heading">PERSISTENT OPERATOR INSTRUCTIONS</div>{operatorInstructions.map(item => <div className="operator-instruction-row" key={item.category}><span><b>{item.category.toUpperCase()}</b>{item.instruction}</span><button onClick={() => void api.deleteOperatorInstruction(item.category).then(result => setOperatorInstructions(result.items || [])).catch(e => setError(e instanceof Error ? e.message : 'Could not remove instruction'))} title="Remove this saved instruction"><X size={13}/></button></div>)}</section>}
          <input className="search-input" placeholder="Search saved memories…" value={memoryQuery} onChange={e => setMemoryQuery(e.target.value)}/>
          <div className="memory-add"><textarea rows={2} placeholder="A fact or preference to remember…" value={memoryDraft} onChange={e => setMemoryDraft(e.target.value)}/><div className="memory-add-row"><select value={memoryCategory} onChange={e => setMemoryCategory(e.target.value)}><option>general</option><option>preference</option><option>workflow</option><option>knowledge</option><option>project</option></select><button className="small-primary" onClick={() => void addMemory()} disabled={!memoryDraft.trim()}><Plus size={14}/> SAVE MEMORY</button></div></div>
          <div className="memory-list">{memories.map(item => <article className="memory-card" key={item.id}><div className="memory-meta"><span>{item.category.toUpperCase()}</span><span>{item.source}</span></div>{editing === item.id ? <><textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={3}/><div className="memory-actions"><button onClick={() => void saveEdit(item)}>SAVE</button><button onClick={() => setEditing(null)}>CANCEL</button></div></> : <><p>{item.content}</p><div className="memory-actions"><button onClick={() => { setEditing(item.id); setEditContent(item.content); }}><Pencil size={12}/> EDIT</button><button className="danger-text" onClick={() => void removeMemory(item.id)}><Trash2 size={12}/> DELETE</button></div></>}</article>)}{!memories.length && <div className="empty-state">No matching memories stored.</div>}</div>
        </div>}
        {panel === 'development' && <DevelopmentLab model={model}/>}
        {panel === 'system' && <div className="system-panel"><div className="eyebrow">LIVE TELEMETRY</div><div className="chat-title">System diagnostics</div><div className="diag-row"><span>OS HOST</span><b>WINDOWS 11</b></div><div className="diag-row"><span>CPU</span><b>AMD RYZEN 7 9800X3D</b></div><div className="diag-row"><span>GPU</span><b>{gpu?.name || 'NVIDIA GPU NOT DETECTED'}</b></div><div className="diag-row"><span>GPU VRAM</span><b>{gpu?.available ? `${fmt((gpu.vram_total_mb || 0) / 1024)} GB total` : 'UNAVAILABLE'}</b></div><div className="diag-row"><span>GPU TEMPERATURE</span><b>{fmt(gpu?.temperature_c, ' °C')}</b></div><div className="diag-row"><span>CPU LOAD</span><b>{fmt(hardware?.cpu_percent, ' %')}</b></div><div className="diag-row"><span>RAM</span><b>{hardware ? `${fmt(hardware.ram_used_gb)} / ${fmt(hardware.ram_total_gb)} GB` : '—'}</b></div><div className="diag-row"><span>OLLAMA</span><b className={status?.ollama_available ? 'good' : 'bad'}>{status?.ollama_available ? 'CONNECTED' : 'OFFLINE'}</b></div><div className="diag-row"><span>INSTALLED MODELS</span><b>{models.length}</b></div><div className="diag-row"><span>NETWORK POLICY</span><b>LOCAL ONLY</b></div><div className="diag-row"><span>API BIND</span><b>127.0.0.1</b></div><div className="diag-note"><ShieldCheck size={16}/> Only the project imports folder is exposed by the starter API. There is no arbitrary command runner.</div></div>}
      </aside>
    </section>
    <footer className="bottomline"><span>J.A.R.V.I.S. / BUILD 0.1.16</span><span>CREATED BY FUNDUH / ERRIS</span><span><Globe2 size={12}/> EXTERNAL NETWORK ACCESS DISABLED</span><span><Mic size={12}/> VOICE: LOCAL WHISPER + CONTINUOUS VAD + KOKORO NEURAL TTS</span><span><TerminalSquare size={12}/> VS CODE WORKSPACE</span></footer>
  </main>;
}
