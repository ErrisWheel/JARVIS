import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Archive, ArrowDownToLine, CheckCircle2, Circle, Clock3, Download, FolderPlus, History, Layers3, ListChecks, LockKeyhole, Play, Plus, RefreshCw, RotateCcw, Search, Shield, ShieldCheck, Square, Star, Trash2, Wrench } from 'lucide-react';
import { api, type ActivityEvent, type ConversationMeta, type LocalSkill, type TaskJob, type ToolPermission, type Workspace } from './api';

type Props = {
  conversationId: string;
  model: string;
  onSelectConversation: (id: string) => void;
  onReplayEvent: (event: ActivityEvent) => void;
};

type Section = 'workspace' | 'tasks' | 'timeline' | 'permissions' | 'skills' | 'backup';

function prettyTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
function sizeLabel(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function OperationsPanel({ conversationId, model, onSelectConversation, onReplayEvent }: Props) {
  const [section, setSection] = useState<Section>('workspace');
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState('default');
  const [showArchivedWorkspaces, setShowArchivedWorkspaces] = useState(false);
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [historyQuery, setHistoryQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [selectedSkillId, setSelectedSkillId] = useState('');
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [goal, setGoal] = useState('');
  const [tasks, setTasks] = useState<TaskJob[]>([]);
  const [activeTaskId, setActiveTaskId] = useState('');
  const [permissions, setPermissions] = useState<ToolPermission[]>([]);
  const [skills, setSkills] = useState<LocalSkill[]>([]);
  const [backups, setBackups] = useState<{ filename: string; size_bytes: number; modified_at: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const activeTask = useMemo(() => tasks.find(task => task.id === activeTaskId) || tasks[0] || null, [activeTaskId, tasks]);

  const loadWorkspaces = useCallback(async () => {
    const result = await api.workspaces(showArchivedWorkspaces);
    setWorkspaces(result.items || []);
    if (result.items?.length && !result.items.some(item => item.id === workspaceId)) setWorkspaceId(result.items[0].id);
  }, [workspaceId, showArchivedWorkspaces]);
  const loadConversations = useCallback(async () => {
    const result = await api.conversations(workspaceId, historyQuery, showArchived);
    setConversations(result.items || []);
  }, [historyQuery, showArchived, workspaceId]);
  const loadTasks = useCallback(async () => {
    const result = await api.taskJobs();
    setTasks(result.items || []);
  }, []);
  const loadEvents = useCallback(async () => {
    const result = await api.activityEvents(conversationId, 200);
    setEvents(result.items || []);
  }, [conversationId]);

  useEffect(() => { void loadWorkspaces().catch(e => setError(e instanceof Error ? e.message : 'Workspace list failed')); }, [loadWorkspaces]);
  useEffect(() => { let active = true; void api.conversations(undefined, '', true).then(result => { const current = result.items.find(item => item.conversation_id === conversationId); if (active && current?.workspace_id) setWorkspaceId(current.workspace_id); }).catch(() => undefined); return () => { active = false; }; }, [conversationId]);
  useEffect(() => { void loadConversations().catch(e => setError(e instanceof Error ? e.message : 'Conversation list failed')); }, [loadConversations]);
  useEffect(() => { void loadTasks().catch(e => setError(e instanceof Error ? e.message : 'Task list failed')); }, [loadTasks]);
  useEffect(() => { void loadEvents().catch(e => setError(e instanceof Error ? e.message : 'Event timeline failed')); }, [loadEvents]);
  useEffect(() => {
    if (!tasks.some(task => task.status === 'running')) return;
    const timer = window.setInterval(() => { void loadTasks().catch(() => undefined); }, 1400);
    return () => window.clearInterval(timer);
  }, [loadTasks, tasks]);
  useEffect(() => {
    if (section === 'permissions') void api.permissions().then(result => setPermissions(result.items || [])).catch(e => setError(e instanceof Error ? e.message : 'Permission list failed'));
    if (section === 'skills') void api.skills().then(result => setSkills(result.items || [])).catch(e => setError(e instanceof Error ? e.message : 'Skill list failed'));
    if (section === 'backup') void api.backups().then(result => setBackups(result.items || [])).catch(e => setError(e instanceof Error ? e.message : 'Backup list failed'));
  }, [section]);

  const createWorkspace = async () => {
    const name = window.prompt('Name the new workspace:');
    if (!name?.trim()) return;
    setBusy(true); setError('');
    try { const result = await api.createWorkspace(name.trim()); setWorkspaceId(result.workspace.id); await loadWorkspaces(); setNotice(`Workspace “${name.trim()}” created.`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create workspace'); }
    finally { setBusy(false); }
  };
  const renameWorkspace = async () => {
    const active = workspaces.find(item => item.id === workspaceId);
    if (!active) return;
    const name = window.prompt('Rename workspace:', active.name);
    if (!name?.trim()) return;
    try { await api.updateWorkspace(active.id, { name: name.trim() }); await loadWorkspaces(); setNotice('Workspace renamed.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Workspace rename failed'); }
  };
  const toggleWorkspaceArchive = async () => {
    const active = workspaces.find(item => item.id === workspaceId);
    if (!active || active.id === 'default') return;
    try {
      await api.updateWorkspace(active.id, { archived: !Boolean(active.archived) });
      if (!active.archived) setWorkspaceId('default');
      await loadWorkspaces();
      setNotice(active.archived ? 'Workspace restored.' : 'Workspace archived. Existing conversations were retained.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Workspace archive update failed'); }
  };
  const createConversation = async () => {
    setBusy(true); setError('');
    try { const result = await api.createConversation(workspaceId); await loadConversations(); onSelectConversation(result.conversation.conversation_id); setNotice('New conversation created.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not create conversation'); }
    finally { setBusy(false); }
  };
  const updateConversation = async (item: ConversationMeta, change: { title?: string; pinned?: boolean; archived?: boolean; workspace_id?: string }) => {
    try { await api.updateConversationMeta(item.conversation_id, change); await loadConversations(); setNotice('Conversation updated.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Conversation update failed'); }
  };
  const exportConversation = async (item: ConversationMeta) => {
    try {
      const data = await api.exportConversation(item.conversation_id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `jarvis-${item.conversation_id}.json`; anchor.click(); URL.revokeObjectURL(url);
      setNotice(`Exported “${item.title}”.`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Conversation export failed'); }
  };
  const planTask = async () => {
    if (goal.trim().length < 8) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.planTask(goal.trim(), conversationId, model, selectedSkillId || undefined);
      setTasks(current => [result.task, ...current.filter(task => task.id !== result.task.id)]);
      setActiveTaskId(result.task.id); setSection('tasks'); setNotice('Plan created. Review every step before approving execution.'); setSelectedSkillId('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Task planning failed'); }
    finally { setBusy(false); }
  };
  const runTask = async (task: TaskJob) => {
    const phrase = `RUN:${task.id}`;
    const entered = window.prompt(`Review the plan, then type this exact approval phrase to execute locally:\n\n${phrase}`);
    if (entered !== phrase) return;
    setBusy(true); setError('');
    try { await api.runTask(task.id, phrase); await loadTasks(); setActiveTaskId(task.id); setNotice('Task accepted. Progress and results are saved locally. Interrupted tasks require your explicit RESUME approval.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not run task'); }
    finally { setBusy(false); }
  };
  const cancelTask = async (task: TaskJob) => {
    try { await api.cancelTask(task.id); await loadTasks(); setNotice('Cancellation requested. The current local step will finish or return before the runner stops.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not cancel task'); }
  };
  const togglePermission = async (permission: ToolPermission) => {
    try { const result = await api.updatePermission(permission.capability, !Boolean(permission.enabled)); setPermissions(result.items); setNotice(`${permission.capability} ${permission.enabled ? 'disabled' : 'enabled'}.`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Permission update failed'); }
  };
  const createBackup = async () => {
    setBusy(true); setError('');
    try { const result = await api.createBackup(); await api.backups().then(data => setBackups(data.items)); setNotice(`Database snapshot created: ${result.backup.filename}`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Database backup failed'); }
    finally { setBusy(false); }
  };
  const restoreBackup = async (filename: string) => {
    const phrase = `RESTORE:${filename}`;
    const entered = window.prompt(`This replaces the active JARVIS database. A safety snapshot will be created first.\n\nType exactly:\n${phrase}`);
    if (entered !== phrase) return;
    setBusy(true); setError('');
    try { const result = await api.restoreBackup(filename, phrase); setNotice(result.notice || 'Database restored. Restart JARVIS.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Database restore failed'); }
    finally { setBusy(false); }
  };

  return <div className="operations-panel">
    <div className="operations-header"><div><div className="eyebrow">LOCAL OPERATIONS / CONTROL PLANE</div><div className="chat-title">JARVIS Operations</div></div><button className="ops-refresh" onClick={() => { void loadWorkspaces(); void loadConversations(); void loadTasks(); void loadEvents(); }} title="Refresh operations"><RefreshCw size={14}/></button></div>
    <div className="ops-tabs">
      <button className={section === 'workspace' ? 'active' : ''} onClick={() => setSection('workspace')}><Layers3 size={12}/> WORKSPACES</button>
      <button className={section === 'tasks' ? 'active' : ''} onClick={() => setSection('tasks')}><ListChecks size={12}/> TASKS</button>
      <button className={section === 'timeline' ? 'active' : ''} onClick={() => setSection('timeline')}><History size={12}/> TIMELINE</button>
      <button className={section === 'permissions' ? 'active' : ''} onClick={() => setSection('permissions')}><Shield size={12}/> PERMISSIONS</button>
      <button className={section === 'skills' ? 'active' : ''} onClick={() => setSection('skills')}><Wrench size={12}/> SKILLS</button>
      <button className={section === 'backup' ? 'active' : ''} onClick={() => setSection('backup')}><DatabaseIcon/> BACKUPS</button>
    </div>
    {error && <div className="inline-error">{error}</div>}{notice && <div className="inline-notice">{notice}</div>}

    {section === 'workspace' && <section className="ops-section">
      <div className="ops-section-head"><b>WORKSPACES</b><div><button onClick={() => setShowArchivedWorkspaces(value => !value)}>{showArchivedWorkspaces ? 'HIDE ARCHIVED' : 'ARCHIVED'}</button><button onClick={() => void renameWorkspace()} disabled={busy || workspaceId === 'default'}>RENAME</button><button onClick={() => void toggleWorkspaceArchive()} disabled={busy || workspaceId === 'default'}>{workspaces.find(item => item.id === workspaceId)?.archived ? 'RESTORE' : 'ARCHIVE'}</button><button onClick={() => void createWorkspace()} disabled={busy}><FolderPlus size={12}/> NEW</button></div></div>
      <div className="ops-workspace-list">{workspaces.map(workspace => <button key={workspace.id} className={workspace.id === workspaceId ? 'ops-workspace active' : 'ops-workspace'} onClick={() => setWorkspaceId(workspace.id)}><span>{workspace.name}</span><small>{workspace.conversation_count} chats{workspace.archived ? ' · ARCHIVED' : ''}</small></button>)}</div>
      <div className="ops-section-head"><b>CONVERSATION HISTORY</b><div><button onClick={() => setShowArchived(value => !value)}>{showArchived ? 'HIDE ARCHIVED' : 'SHOW ARCHIVED'}</button><button onClick={() => void createConversation()} disabled={busy || Boolean(workspaces.find(item => item.id === workspaceId)?.archived)} title={workspaces.find(item => item.id === workspaceId)?.archived ? 'Restore this workspace before creating a chat' : 'Create a conversation in this workspace'}><Plus size={12}/> NEW CHAT</button></div></div>
      <div className="ops-search"><Search size={13}/><input value={historyQuery} onChange={e => setHistoryQuery(e.target.value)} placeholder="Search titles and messages…"/></div>
      <div className="ops-conversation-list">{conversations.map(item => <article key={item.conversation_id} className={item.conversation_id === conversationId ? 'ops-conversation current' : 'ops-conversation'}>
        <button className="ops-conversation-select" onClick={() => onSelectConversation(item.conversation_id)}><span>{item.pinned ? <Star size={11} className="ops-star"/> : <MessageIcon/>}{item.title}</span><small>{item.message_count} messages · {prettyTime(item.updated_at)}</small></button>
        <div className="ops-conversation-actions"><button title="Pin/unpin" onClick={() => void updateConversation(item, { pinned: !Boolean(item.pinned) })}><Star size={11}/></button><button title="Rename" onClick={() => { const title = window.prompt('Conversation title:', item.title); if (title?.trim()) void updateConversation(item, { title: title.trim() }); }}><PencilIcon/></button><button title="Export JSON" onClick={() => void exportConversation(item)}><Download size={11}/></button>{item.workspace_id !== workspaceId && <button title="Move to this workspace" onClick={() => void updateConversation(item, { workspace_id: workspaceId })}><Layers3 size={11}/></button>}{item.archived ? <button title="Restore from archive" onClick={() => void updateConversation(item, { archived: false })}><RotateCcw size={11}/></button> : <button title="Archive" onClick={() => void updateConversation(item, { archived: true })}><Archive size={11}/></button>}</div>
      </article>)}{!conversations.length && <div className="ops-empty">No conversations in this workspace.</div>}</div>
      <p className="ops-footnote">Conversations are retained in the local SQLite database. Archived conversations can be restored; exporting creates a portable JSON copy.</p>
    </section>}

    {section === 'tasks' && <section className="ops-section">
      <div className="ops-section-head"><b>SUPERVISED TASK ORCHESTRATOR</b><span className="ops-local-tag"><LockKeyhole size={10}/> LOCAL ONLY</span></div>
      <p className="muted small">JARVIS can plan a multi-step task, retrieve local memories/documents, and run reasoning steps sequentially. Every plan requires your explicit approval. No shell or internet tool is available.</p>
      <textarea className="ops-task-goal" rows={3} maxLength={4000} value={goal} onChange={event => setGoal(event.target.value)} placeholder="Describe a multi-step task for JARVIS…"/>
      <button className="small-primary" onClick={() => void planTask()} disabled={busy || goal.trim().length < 8}>{busy ? 'WORKING…' : 'CREATE LOCAL PLAN'}</button>
      <div className="ops-task-list">{tasks.map(task => <article className={activeTask?.id === task.id ? 'ops-task active' : 'ops-task'} key={task.id}>
        <button className="ops-task-head" onClick={() => setActiveTaskId(task.id)}><span>{task.goal.slice(0, 100)}</span><small>{task.status.toUpperCase()} · {prettyTime(task.updated_at)}</small></button>
        {activeTask?.id === task.id && <div className="ops-task-body">
          {task.error && <div className="inline-error">{task.error}</div>}
          {task.plan.map(step => <div className="ops-task-step" key={step.index}><span>{step.status === 'complete' ? <CheckCircle2 size={12}/> : step.status === 'running' ? <Clock3 size={12}/> : step.status === 'failed' ? <Trash2 size={12}/> : <Circle size={12}/>}</span><div><b>{step.index}. {step.title}</b><small>{step.capability} · {step.instruction}</small></div></div>)}
          {task.results.map(result => <details className="ops-task-result" key={result.index}><summary>{result.index}. {result.title} · RESULT</summary><pre>{result.output}</pre></details>)}
          <div className="ops-task-actions">{['planned','interrupted','failed'].includes(task.status) && <button className="small-primary" onClick={() => void runTask(task)} disabled={busy}><Play size={12}/> {task.status === 'interrupted' ? 'RESUME TASK' : 'APPROVE & RUN'}</button>}{task.status === 'running' && <button onClick={() => void cancelTask(task)}><Square size={11}/> CANCEL</button>}</div>
        </div>}
      </article>)}{!tasks.length && <div className="ops-empty">No saved tasks yet.</div>}</div>
      <p className="ops-footnote">Running tasks are persisted. If JARVIS restarts mid-task, they are marked interrupted and wait for your manual review and resume approval.</p>
    </section>}

    {section === 'timeline' && <section className="ops-section">
      <div className="ops-section-head"><b>RECORDED ACTIVITY</b><button onClick={() => void loadEvents()}><RefreshCw size={11}/> REFRESH</button></div>
      <p className="muted small">This timeline contains backend-recorded events, not generated descriptions of private model thoughts. Select an event to replay its stage on the holographic interface.</p>
      <div className="ops-event-list">{events.map(event => <article className="ops-event" key={event.id}><div className="ops-event-marker"><Activity size={12}/></div><div className="ops-event-content"><b>{event.title}</b><small>{event.event_type} · {prettyTime(event.created_at)}</small><p>{Object.entries(event.payload || {}).map(([key,value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`).join(' · ')}</p><button onClick={() => onReplayEvent(event)}>REPLAY IN HOLOGRAM</button></div></article>)}{!events.length && <div className="ops-empty">No recorded activity for this conversation yet. Start a chat request to populate the timeline.</div>}</div>
    </section>}

    {section === 'permissions' && <section className="ops-section">
      <div className="ops-section-head"><b>TOOL PERMISSION MANAGER</b><span className="ops-local-tag"><ShieldCheck size={10}/> POLICY ENFORCED</span></div>
      <p className="muted small">These settings are enforced at backend route boundaries for supported local capabilities. Authentication, import-path checks, model availability, and operator confirmations remain independent safeguards.</p>
      {permissions.map(permission => <div className="ops-permission" key={permission.capability}><div><b>{permission.capability.replace(/_/g,' ').toUpperCase()}</b><small>{permission.description}{permission.requires_approval ? ' · APPROVAL REQUIRED' : ''}</small></div><label><input type="checkbox" checked={Boolean(permission.enabled)} onChange={() => void togglePermission(permission)} disabled={['external_network','shell_execution'].includes(permission.capability)}/><span>{['external_network','shell_execution'].includes(permission.capability) ? 'LOCKED OFF' : permission.enabled ? 'ENABLED' : 'DISABLED'}</span></label></div>)}
      <div className="ops-security-note"><LockKeyhole size={13}/> External internet and arbitrary shell execution are intentionally unavailable in this local build and cannot be enabled here.</div>
    </section>}

    {section === 'skills' && <section className="ops-section">
      <div className="ops-section-head"><b>LOCAL SKILL REGISTRY</b><span className="ops-local-tag">DECLARATIVE</span></div>
      <p className="muted small">Drop a manifest.json into F:\JARVIS\skills\your-skill\. JARVIS reads the manifest as metadata only; this registry does not load or execute arbitrary extension code.</p>
      {skills.map(skill => <article className="ops-skill" key={skill.id}><b>{skill.name}</b><small>{skill.id}</small><p>{skill.description}</p><span>{skill.capabilities.join(' · ') || 'No supported capabilities declared'}</span><button className="small-primary" onClick={() => { setSelectedSkillId(skill.id); setGoal(`${skill.name}: ${skill.description}\n\nPlease apply this local workflow to the following task: `); setSection('tasks'); }}>USE SKILL IN TASK PLANNER</button></article>)}
      {!skills.length && <div className="ops-empty">No local skill manifests have been added yet. The registry is ready for declarative skills.</div>}
    </section>}

    {section === 'backup' && <section className="ops-section">
      <div className="ops-section-head"><b>DATABASE SNAPSHOTS</b><button className="small-primary" onClick={() => void createBackup()} disabled={busy}><Plus size={12}/> CREATE SNAPSHOT</button></div>
      <p className="muted small">Creates a consistent SQLite snapshot under F:\JARVIS\data\backups. Restoring automatically takes a snapshot of the current database first. Restart JARVIS after a restore.</p>
      {backups.map(backup => <article className="ops-backup" key={backup.filename}><div><b>{backup.filename}</b><small>{sizeLabel(backup.size_bytes)} · {prettyTime(backup.modified_at)}</small></div><div><button onClick={() => { const a = document.createElement('a'); a.href = `/api/backups/${encodeURIComponent(backup.filename)}`; a.download = backup.filename; a.click(); }} title="Download snapshot"><ArrowDownToLine size={12}/></button><button className="danger-text" onClick={() => void restoreBackup(backup.filename)} title="Restore snapshot"><RotateCcw size={12}/></button></div></article>)}
      {!backups.length && <div className="ops-empty">No snapshots yet. Create one before a major update.</div>}
    </section>}
  </div>;
}

function MessageIcon() { return <span className="ops-message-dot"/>; }
function PencilIcon() { return <span className="ops-pencil">EDIT</span>; }
function DatabaseIcon() { return <span className="ops-database-icon">DB</span>; }
