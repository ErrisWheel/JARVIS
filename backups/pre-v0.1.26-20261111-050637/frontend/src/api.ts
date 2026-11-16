export type Hardware = {
  cpu_percent: number; ram_total_gb: number; ram_used_gb: number; ram_percent: number;
  gpu: { available: boolean; name?: string; utilization_percent?: number | null; vram_used_mb?: number | null;
    vram_total_mb?: number | null; temperature_c?: number | null; power_w?: number | null; error?: string };
};
export type Memory = { id: number; content: string; category: string; source: string; tags: string; created_at: string; updated_at: string };
export type ModelInfo = { name: string; size?: number };
export type ModelTeamStatus = { available: boolean; enabled: boolean; primary?: string; reviewer?: string | null; installed?: string[]; vision_specialist?: string | null; image_generator?: string | null; speech_recognition?: string | null; speech_synthesis?: string | null; scheduling?: string; error?: string };
export type VoiceDevice = { index: number; name: string; channels: number; default: boolean };
export type VoiceEvent = { type: string; text?: string; language?: string | null; message?: string; state?: string; error?: string };
export type MicTelemetry = { input_level: number; input_threshold_level: number; input_signal: boolean; input_dbfs: number; queue_depth: number; device_name?: string };
export type ActivityNode = {
  id: 'input' | 'memory' | 'model' | 'response';
  status: 'idle' | 'active' | 'complete' | 'warning';
  title: string;
  summary: string;
  details: string;
};
export type StyleProfile = {
  samples: number; average_words: number; tone: string; language: string; brevity: string;
  expression: string; humor?: string; profanity_tolerance?: string;
};
export type StyleSettings = { enabled: boolean; profile: StyleProfile | Record<string, never> };
export type OperatorInstruction = { category: string; instruction: string; source: string; updated_at: string };
export type ImageProgressEvent = {
  type: 'stage' | 'progress' | 'heartbeat' | 'complete' | 'error';
  stage?: string; label?: string; percent?: number | null;
  step?: number; total_steps?: number; elapsed_seconds?: number;
  eta_seconds?: number | null; step_seconds?: number; job_elapsed_seconds?: number;
  filename?: string; svg_filename?: string | null; url?: string; prompt?: string; width?: number; height?: number;
  size_bytes?: number; message?: string; error?: string;
};

export type DevFileInfo = { path: string; description: string; size: number; sha256: string };
export type DevChange = { path: string; reason: string; diff: string };
export type DevProposal = {
  id: string; summary: string; warnings: string[]; status: 'pending' | 'applied' | 'rolled_back';
  created_at: string; confirmation_required: string; changes: DevChange[];
};
export type DevKnowledgeItem = { id: string; category: string; content: string; created_at: string; source: string };

function describeApiError(body: any, fallback: string): string {
  const detail = body?.detail ?? body?.error;
  if (Array.isArray(detail)) {
    const issues = detail.map((item: any) => {
      const location = Array.isArray(item?.loc) ? item.loc.join('.') : 'request';
      const message = typeof item?.msg === 'string' ? item.msg : 'Invalid value';
      return `${location}: ${message}`;
    }).filter(Boolean);
    return issues.length ? issues.join('; ') : fallback;
  }
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (typeof body?.message === 'string' && body.message.trim()) return body.message;
  return fallback;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(describeApiError(body, `Request failed (${response.status})`));
  return body as T;
}

export const api = {
  status: () => request<any>('/api/status'),
  hardware: () => request<Hardware>('/api/hardware'),
  models: () => request<{ available: boolean; models: ModelInfo[]; error?: string }>('/api/models'),
  modelTeam: () => request<ModelTeamStatus>('/api/model-team'),
  conversation: (id: string) => request<{ messages: { role: 'user' | 'assistant'; content: string; image_filename?: string; image_available?: boolean; image_prompt?: string; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage' | null; svg_available?: boolean }[] }>(`/api/conversations/${encodeURIComponent(id)}`),
  chat: (payload: { message: string; conversation_id: string; mode: string; model: string }) =>
    request<{ answer: string; model: string; auto_memory_saved: boolean; memory_notice?: string }>('/api/chat', { method: 'POST', body: JSON.stringify(payload) }),
  explainAnswer: (payload: { question: string; answer: string; conversation_id: string; model: string }) =>
    request<{ explanation: string; model: string; memory_excerpts_supplied: number }>('/api/chat/explain', { method: 'POST', body: JSON.stringify(payload) }),
  chatStream: async (
    payload: { message: string; conversation_id: string; mode: string; model: string; voice_mode?: boolean },
    onDelta: (text: string) => void,
    onActivity?: (activity: ActivityNode) => void,
    signal?: AbortSignal,
  ): Promise<{ answer: string; memory_notice?: string; auto_memory_saved?: boolean; incomplete?: boolean }> => {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(describeApiError(body, `Chat request failed (${response.status})`));
    }
    if (!response.body) throw new Error('Streaming responses are not supported by this browser.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    let answer = '';
    let completion: { answer?: string; memory_notice?: string; auto_memory_saved?: boolean; incomplete?: boolean } = {};
    const processLine = (line: string) => {
      if (!line.trim()) return;
      const event = JSON.parse(line) as { type: string; text?: string; answer?: string; error?: string; memory_notice?: string; auto_memory_saved?: boolean; node?: ActivityNode['id']; status?: ActivityNode['status']; title?: string; summary?: string; details?: string };
      if (event.type === 'activity' && event.node && event.status) {
        onActivity?.({ id: event.node, status: event.status, title: event.title || event.node, summary: event.summary || '', details: event.details || '' });
      } else if (event.type === 'delta' && event.text) {
        answer += event.text;
        onDelta(event.text);
      } else if (event.type === 'done') {
        completion = event;
        if (event.answer) answer = event.answer;
      } else if (event.type === 'error') {
        throw new Error(event.error || 'Local model streaming failed.');
      }
    };

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        const lines = pending.split('\n');
        pending = lines.pop() || '';
        for (const line of lines) processLine(line);
      }
      pending += decoder.decode();
      if (pending.trim()) processLine(pending);
    } finally {
      reader.releaseLock();
    }
    if (!answer.trim()) throw new Error('The local model returned an empty response.');
    return { answer, memory_notice: completion.memory_notice, auto_memory_saved: completion.auto_memory_saved, incomplete: completion.incomplete };
  },
  memories: (q = '') => request<{ items: Memory[]; count: number }>(`/api/memories?q=${encodeURIComponent(q)}`),
  addMemory: (payload: { content: string; category: string; tags: string }) => request<{ id: number }>('/api/memories', { method: 'POST', body: JSON.stringify(payload) }),
  updateMemory: (id: number, payload: { content: string; category: string; tags: string }) => request(`/api/memories/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteMemory: (id: number) => request(`/api/memories/${id}`, { method: 'DELETE' }),
  imageStatus: () => request<{ available: boolean; poster_available?: boolean; runtime_installed: boolean; model_installed: boolean; output_directory: string }>('/api/images/status'),
  generateImage: (payload: { prompt: string; conversation_id: string; width?: number; height?: number; steps?: number; seed?: number; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage'; poster_operation?: 'new' | 'refine' | 'redesign'; previous_poster_filename?: string; poster_source_prompt?: string; poster_design_notes?: string; poster_visual_style?: 'default' | 'artsy' | 'technical' | 'vintage' | 'museum' | 'collage' | 'watercolor' | 'minimal'; poster_visual_density?: 'normal' | 'rich' | 'high'; design_seed?: number }) =>
    request<{ ok: boolean; filename: string; url: string; prompt: string; width: number; height: number; message: string }>('/api/images/generate', { method: 'POST', body: JSON.stringify(payload) }),
  generateImageStream: async (
    payload: { prompt: string; conversation_id: string; width?: number; height?: number; steps?: number; seed?: number; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage'; poster_operation?: 'new' | 'refine' | 'redesign'; previous_poster_filename?: string; poster_source_prompt?: string; poster_design_notes?: string; poster_visual_style?: 'default' | 'artsy' | 'technical' | 'vintage' | 'museum' | 'collage' | 'watercolor' | 'minimal'; poster_visual_density?: 'normal' | 'rich' | 'high'; design_seed?: number },
    onEvent: (event: ImageProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<Required<Pick<ImageProgressEvent, 'filename' | 'url' | 'prompt' | 'width' | 'height' | 'elapsed_seconds'>> & ImageProgressEvent> => {
    const response = await fetch('/api/images/generate/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(describeApiError(body, `Image generation failed (${response.status})`));
    }
    if (!response.body) throw new Error('Streaming image progress is not supported by this browser.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    const streamState: { completed?: ImageProgressEvent } = {};
    const processLine = (line: string) => {
      if (!line.trim()) return;
      const event = JSON.parse(line) as ImageProgressEvent;
      onEvent(event);
      if (event.type === 'error') throw new Error(event.error || 'Local image generation failed.');
      if (event.type === 'complete') streamState.completed = event;
    };
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        const records = pending.split('\n');
        pending = records.pop() || '';
        for (const record of records) processLine(record);
      }
      pending += decoder.decode();
      if (pending.trim()) processLine(pending);
    } finally {
      reader.releaseLock();
    }
    const completed = streamState.completed;
    if (!completed?.filename || !completed.url) throw new Error('Image worker ended without a verified completed-image event.');
    return completed as Required<Pick<ImageProgressEvent, 'filename' | 'url' | 'prompt' | 'width' | 'height' | 'elapsed_seconds'>> & ImageProgressEvent;
  },
  analyzeGeneratedImage: (payload: { filename: string; question: string; conversation_id: string }) =>
    request<{ ok: boolean; answer: string; model: string; filename: string }>('/api/images/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  imageVisionStatus: () => request<{ available: boolean; installed: boolean; model: string; download_size?: string }>('/api/images/vision-status'),
  generatedImagesIndex: () => request<{ png: string[]; svg: string[] }>('/api/generated-images/index'),
  generatedImage: async (filename: string): Promise<Blob> => {
    if (!/^[a-f0-9]{32}\.png$/i.test(filename)) throw new Error('Invalid generated image filename.');
    const response = await fetch(`/api/generated-images/${encodeURIComponent(filename)}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(describeApiError(body, `Could not load generated image (${response.status}).`));
    }
    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) throw new Error('The generated image endpoint did not return an image.');
    return blob;
  },
  generatedSvg: async (filename: string): Promise<Blob> => {
    if (!/^[a-f0-9]{32}\.svg$/i.test(filename)) throw new Error('Invalid generated SVG filename.');
    const response = await fetch(`/api/generated-svgs/${encodeURIComponent(filename)}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(describeApiError(body, `Could not load generated SVG (${response.status}).`));
    }
    const blob = await response.blob();
    if (blob.type !== 'image/svg+xml' || blob.size < 1000) throw new Error('The generated vector file is not a valid SVG poster.');
    return blob;
  },
  selfDevelopmentFiles: () => request<{ items: DevFileInfo[]; protected_files: string[]; approval_required: boolean; shell_access: boolean }>('/api/self-development/files'),
  selfDevelopmentKnowledge: () => request<{ items: DevKnowledgeItem[]; count: number; max_items: number }>('/api/self-development/knowledge'),
  addSelfDevelopmentKnowledge: (content: string, category: string) => request<{ ok: boolean; item: DevKnowledgeItem }>('/api/self-development/knowledge', { method: 'POST', body: JSON.stringify({ content, category }) }),
  deleteSelfDevelopmentKnowledge: (itemId: string) => request<{ ok: boolean; deleted: string }>(`/api/self-development/knowledge/${encodeURIComponent(itemId)}`, { method: 'DELETE' }),
  proposeSelfDevelopment: (payload: { goal: string; files: string[]; model: string }) =>
    request<DevProposal>('/api/self-development/propose', { method: 'POST', body: JSON.stringify(payload) }),
  applySelfDevelopment: (proposal_id: string, confirmation: string) =>
    request<{ ok: boolean; proposal_id: string; status: string; files: string[]; backup_directory: string }>('/api/self-development/apply', { method: 'POST', body: JSON.stringify({ proposal_id, confirmation }) }),
  rollbackSelfDevelopment: (proposal_id: string, confirmation: string) =>
    request<{ ok: boolean; proposal_id: string; status: string; files: string[] }>('/api/self-development/rollback', { method: 'POST', body: JSON.stringify({ proposal_id, confirmation }) }),
  style: () => request<StyleSettings>('/api/style'),
  updateStyle: (enabled: boolean) => request<StyleSettings>('/api/style', { method: 'PUT', body: JSON.stringify({ enabled }) }),
  operatorInstructions: () => request<{ items: OperatorInstruction[] }>('/api/instructions'),
  deleteOperatorInstruction: (category: string) => request<{ ok: boolean; items: OperatorInstruction[] }>(`/api/instructions/${encodeURIComponent(category)}`, { method: 'DELETE' }),
  exportCode: async (content: string): Promise<Blob> => {
    const response = await fetch('/api/exports/code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Code export failed (${response.status})`); }
    return response.blob();
  },
  transcribe: async (audio: Blob) => {
    const form = new FormData();
    form.append('audio', audio, 'jarvis-recording.webm');
    const response = await fetch('/api/transcribe', { method: 'POST', body: form });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Voice transcription failed (${response.status})`);
    return body as { text: string; language?: string | null };
  },
  voiceDevices: () => request<{ items: VoiceDevice[]; default_input: number | null }>('/api/voice/devices'),
  voiceStatus: () => request<any>('/api/voice/status'),
  startVoiceListener: (device_index: number | null, mode: 'wake' | 'conversation' = 'conversation') => request<any>('/api/voice/start', { method: 'POST', body: JSON.stringify({ device_index, mode }) }),
  pauseVoiceListener: () => request<any>('/api/voice/pause', { method: 'POST' }),
  resumeVoiceListener: (follow_up_seconds = 0) => request<any>('/api/voice/resume', { method: 'POST', body: JSON.stringify({ follow_up_seconds }) }),
  stopVoiceListener: () => request<any>('/api/voice/stop', { method: 'POST' }),
  setVoiceSpeaking: (speaking: boolean) => request<any>('/api/voice/speaking', { method: 'POST', body: JSON.stringify({ speaking }) }),
  voiceEvents: () => request<{ events: VoiceEvent[]; listener: any }>('/api/voice/events'),
  statusSpeech: async (key: 'ack' | 'working', voice: string, speed = 1.12, signal?: AbortSignal): Promise<Blob> => {
    const response = await fetch(`/api/tts/status-audio/${key}?voice=${encodeURIComponent(voice)}&speed=${encodeURIComponent(String(speed))}`, { signal });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(describeApiError(body, `Local voice status failed (${response.status})`));
    }
    const audio = await response.blob();
    if (!audio.size || !audio.type.includes('audio')) throw new Error('The local voice engine returned an invalid status audio file.');
    return audio;
  },
  synthesizeSpeech: async (text: string, voice: string, speed = 1.12, signal?: AbortSignal): Promise<Blob> => {
    const allowedVoices = new Set(['bm_george', 'bm_lewis', 'am_michael', 'am_adam']);
    const safeText = String(text ?? '').trim();
    const safeVoice = allowedVoices.has(voice) ? voice : 'am_michael';
    const numericSpeed = Number(speed);
    const safeSpeed = Number.isFinite(numericSpeed) ? Math.min(1.15, Math.max(0.85, numericSpeed)) : 1.12;
    if (!safeText) throw new Error('The speech segment is empty.');
    if (safeText.length > 1400) throw new Error(`The speech segment is too long (${safeText.length} characters; maximum 1400).`);
    const response = await fetch('/api/tts/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: safeText, voice: safeVoice, speed: safeSpeed }),
      signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(`Local neural voice failed (${response.status}): ${describeApiError(body, 'Unknown synthesis error')} [voice=${safeVoice}, speed=${safeSpeed}, characters=${safeText.length}]`);
    }
    const audio = await response.blob();
    if (!audio.size || !audio.type.includes('audio')) throw new Error('The local voice engine returned an invalid audio file.');
    return audio;
  },
};
