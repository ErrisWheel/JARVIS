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
export type Workspace = { id: string; name: string; archived: number; created_at: string; updated_at: string; conversation_count: number };
export type ConversationMeta = { conversation_id: string; workspace_id: string; title: string; pinned: number; archived: number; created_at: string; updated_at: string; message_count: number };
export type ActivityEvent = { id: number; conversation_id: string; event_type: string; title: string; payload: Record<string, unknown>; created_at: string };
export type TaskPlan = { index: number; title: string; instruction: string; capability: string; status: string };
export type TaskResult = { index: number; title: string; capability: string; output: string };
export type TaskJob = { id: string; conversation_id: string; goal: string; model: string; status: string; plan: TaskPlan[]; results: TaskResult[]; error: string; created_at: string; updated_at: string; summary?: string };
export type ToolPermission = { capability: string; enabled: number; requires_approval: number; description: string; updated_at: string };
export type LocalSkill = { id: string; name: string; description: string; capabilities: string[]; prompt_template?: string; source: string };
export type AttachedImage = { name: string; original_name: string; size_bytes: number; type: string; previewUrl?: string };

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
  conversation: (id: string) => request<{ messages: { role: 'user' | 'assistant'; content: string; image_filename?: string; image_available?: boolean; image_prompt?: string; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage' | null; orientation?: 'portrait' | 'landscape' | null; svg_available?: boolean }[] }>(`/api/conversations/${encodeURIComponent(id)}`),
  workspaces: (includeArchived = false) => request<{ items: Workspace[] }>(`/api/workspaces?include_archived=${includeArchived}`),
  createWorkspace: (name: string) => request<{ ok: boolean; workspace: Workspace }>('/api/workspaces', { method: 'POST', body: JSON.stringify({ name }) }),
  updateWorkspace: (id: string, payload: { name?: string; archived?: boolean }) => request<{ ok: boolean; workspace: Workspace }>(`/api/workspaces/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  conversations: (workspaceId?: string, query = '', includeArchived = false) => { const params = new URLSearchParams(); if (workspaceId) params.set('workspace_id', workspaceId); params.set('q', query); params.set('include_archived', String(includeArchived)); return request<{ items: ConversationMeta[] }>(`/api/conversations?${params.toString()}`); },
  createConversation: (workspace_id: string, title = 'New conversation') => request<{ ok: boolean; conversation: ConversationMeta }>('/api/conversations', { method: 'POST', body: JSON.stringify({ workspace_id, title }) }),
  updateConversationMeta: (id: string, payload: { title?: string; pinned?: boolean; archived?: boolean; workspace_id?: string }) => request<{ ok: boolean; conversation: ConversationMeta }>(`/api/conversations/${encodeURIComponent(id)}/meta`, { method: 'PATCH', body: JSON.stringify(payload) }),
  exportConversation: (id: string) => request<{ conversation: ConversationMeta; messages: { role: string; content: string }[] }>(`/api/conversations/${encodeURIComponent(id)}/export`),
  activityEvents: (id: string, limit = 100) => request<{ items: ActivityEvent[] }>(`/api/events?conversation_id=${encodeURIComponent(id)}&limit=${limit}`),
  taskJobs: () => request<{ items: TaskJob[] }>('/api/tasks'),
  planTask: (goal: string, conversation_id: string, model: string, skill_id?: string) => request<{ ok: boolean; task: TaskJob }>('/api/tasks/plan', { method: 'POST', body: JSON.stringify({ goal, conversation_id, model, skill_id }) }),
  runTask: (id: string, confirmation: string) => request<{ ok: boolean; accepted?: boolean; task: TaskJob }>(`/api/tasks/${encodeURIComponent(id)}/run`, { method: 'POST', body: JSON.stringify({ confirmation }) }),
  cancelTask: (id: string) => request<{ ok: boolean; task: TaskJob }>(`/api/tasks/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  permissions: () => request<{ items: ToolPermission[]; local_only: boolean }>('/api/permissions'),
  updatePermission: (capability: string, enabled: boolean) => request<{ ok: boolean; items: ToolPermission[] }>(`/api/permissions/${encodeURIComponent(capability)}`, { method: 'PUT', body: JSON.stringify({ enabled }) }),
  skills: () => request<{ items: LocalSkill[]; execution: string }>('/api/skills'),
  createBackup: () => request<{ ok: boolean; backup: { filename: string; size_bytes: number; created_at: string } }>('/api/backups', { method: 'POST' }),
  backups: () => request<{ items: { filename: string; size_bytes: number; modified_at: string }[] }>('/api/backups'),
  restoreBackup: (filename: string, confirmation: string) => request<{ ok: boolean; notice: string }>(`/api/backups/${encodeURIComponent(filename)}/restore`, { method: 'POST', body: JSON.stringify({ confirmation }) }),
  semanticMemoryStatus: () => request<{ configured: boolean; available: boolean; model?: string; indexed: number; fallback?: string; error?: string }>('/api/memory/semantic-status'),
  indexSemanticMemory: (conversationId = 'main') => request<{ ok: boolean; indexed: number; model: string; graph_nodes?: number; graph_links?: number }>(`/api/memory/semantic-index?conversation_id=${encodeURIComponent(conversationId)}`, { method: 'POST' }),
  searchSemanticMemory: (q: string, limit = 8, conversationId = 'main') => request<{ items: Memory[]; mode?: string; warning?: string }>(`/api/memory/semantic-search?q=${encodeURIComponent(q)}&limit=${limit}&conversation_id=${encodeURIComponent(conversationId)}`),
  memoryGraph: (limit = 250, conversationId = 'main') => request<{ available: boolean; model?: string; nodes: { id: number; label: string; category: string; tags: string; updated_at: string }[]; edges: { source: number; target: number; similarity: number }[]; fallback?: string }>(`/api/memory/graph?limit=${limit}&conversation_id=${encodeURIComponent(conversationId)}`),
  importImage: async (file: File, conversationId = 'main'): Promise<AttachedImage> => {
    const form = new FormData(); form.append('file', file, file.name); form.append('conversation_id', conversationId);
    const response = await fetch('/api/images/import', { method: 'POST', body: form });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(describeApiError(body, `Image import failed (${response.status})`));
    return body as AttachedImage;
  },
  chat: (payload: { message: string; conversation_id: string; mode: string; model: string; document_filename?: string; image_filename?: string }) =>
    request<{ answer: string; model: string; auto_memory_saved: boolean; memory_notice?: string }>('/api/chat', { method: 'POST', body: JSON.stringify(payload) }),
  explainAnswer: (payload: { question: string; answer: string; conversation_id: string; model: string }) =>
    request<{ explanation: string; model: string; memory_excerpts_supplied: number }>('/api/chat/explain', { method: 'POST', body: JSON.stringify(payload) }),
  chatStream: async (
    payload: { message: string; conversation_id: string; mode: string; model: string; voice_mode?: boolean; document_filename?: string; image_filename?: string },
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
  importDocument: async (file: File, conversationId = 'main') => {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('conversation_id', conversationId);
    const response = await fetch('/api/documents/import', { method: 'POST', body: form });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(describeApiError(body, `Document import failed (${response.status})`));
    return body as { name: string; original_name: string; size_bytes: number; citations: string[]; parser: string; characters: number; truncated: boolean; executed: false };
  },
  memories: (q = '', conversationId = 'main') => request<{ items: Memory[]; count: number; workspace_id?: string }>(`/api/memories?q=${encodeURIComponent(q)}&conversation_id=${encodeURIComponent(conversationId)}`),
  addMemory: (payload: { content: string; category: string; tags: string; conversation_id?: string }) => request<{ id: number }>('/api/memories', { method: 'POST', body: JSON.stringify(payload) }),
  updateMemory: (id: number, payload: { content: string; category: string; tags: string; conversation_id?: string }) => request(`/api/memories/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteMemory: (id: number, conversationId = 'main') => request(`/api/memories/${id}?conversation_id=${encodeURIComponent(conversationId)}`, { method: 'DELETE' }),
  imageStatus: () => request<{ available: boolean; poster_available?: boolean; runtime_installed: boolean; model_installed: boolean; output_directory: string }>('/api/images/status'),
  generateImage: (payload: { prompt: string; conversation_id: string; width?: number; height?: number; steps?: number; seed?: number; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage'; poster_operation?: 'new' | 'refine' | 'redesign'; previous_poster_filename?: string; poster_source_prompt?: string; poster_design_notes?: string; poster_visual_style?: 'default' | 'artsy' | 'technical' | 'vintage' | 'museum' | 'collage' | 'watercolor' | 'minimal'; poster_visual_density?: 'normal' | 'rich' | 'high'; orientation?: 'portrait' | 'landscape'; design_seed?: number }) =>
    request<{ ok: boolean; filename: string; url: string; prompt: string; width: number; height: number; message: string }>('/api/images/generate', { method: 'POST', body: JSON.stringify(payload) }),
  generateImageStream: async (
    payload: { prompt: string; conversation_id: string; width?: number; height?: number; steps?: number; seed?: number; poster?: boolean; design_variant?: 'cards' | 'timeline' | 'orbit' | 'blueprint' | 'museum' | 'fieldnotes' | 'collage'; poster_operation?: 'new' | 'refine' | 'redesign'; previous_poster_filename?: string; poster_source_prompt?: string; poster_design_notes?: string; poster_visual_style?: 'default' | 'artsy' | 'technical' | 'vintage' | 'museum' | 'collage' | 'watercolor' | 'minimal'; poster_visual_density?: 'normal' | 'rich' | 'high'; orientation?: 'portrait' | 'landscape'; design_seed?: number },
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
