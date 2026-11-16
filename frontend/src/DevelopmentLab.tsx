import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Code2, FileCode2, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react';
import {
  api,
  type DevFileInfo,
  type DevProposal,
  type DevKnowledgeItem,
} from './api';

type Props = { model: string };

export default function DevelopmentLab({ model }: Props) {
  const [files, setFiles] = useState<DevFileInfo[]>([]);
  const [knowledge, setKnowledge] = useState<DevKnowledgeItem[]>([]);
  const [knowledgeDraft, setKnowledgeDraft] = useState('');
  const [knowledgeCategory, setKnowledgeCategory] = useState('project convention');
  const [savingKnowledge, setSavingKnowledge] = useState(false);
  const [selected, setSelected] = useState<string[]>(['frontend/src/Hologram.tsx']);
  const [goal, setGoal] = useState('Improve the hologram node interactions without changing any security or permission behavior.');
  const [proposal, setProposal] = useState<DevProposal | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadFiles = async () => {
    try {
      const result = await api.selfDevelopmentFiles();
      setFiles(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the editable source list.');
    }
  };

  const loadKnowledge = async () => {
    try {
      const result = await api.selfDevelopmentKnowledge();
      setKnowledge(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the coding notebook.');
    }
  };

  useEffect(() => { void loadFiles(); void loadKnowledge(); }, []);

  const saveKnowledge = async () => {
    setSavingKnowledge(true); setError(''); setNotice('');
    try {
      await api.addSelfDevelopmentKnowledge(knowledgeDraft, knowledgeCategory);
      setKnowledgeDraft('');
      await loadKnowledge();
      setNotice('Coding lesson saved locally. Future code proposals will receive it as project guidance.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the coding lesson.');
    } finally {
      setSavingKnowledge(false);
    }
  };

  const removeKnowledge = async (item: DevKnowledgeItem) => {
    try {
      await api.deleteSelfDevelopmentKnowledge(item.id);
      await loadKnowledge();
      setNotice('Coding lesson removed from the local notebook.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove the coding lesson.');
    }
  };

  const toggleFile = (path: string) => {
    setSelected(current => current.includes(path)
      ? current.filter(item => item !== path)
      : current.length < 2 ? [...current, path] : current);
  };

  const createProposal = async () => {
    setBusy(true); setError(''); setNotice(''); setProposal(null); setConfirmation('');
    try {
      const result = await api.proposeSelfDevelopment({ goal, files: selected, model });
      setProposal(result);
      setNotice('Proposal created. Nothing has been changed yet. Review every diff before approving.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The local model could not create a proposal.');
    } finally {
      setBusy(false);
    }
  };

  const applyProposal = async () => {
    if (!proposal || confirmation !== proposal.confirmation_required) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.applySelfDevelopment(proposal.id, confirmation);
      setProposal({ ...proposal, status: 'applied' });
      setConfirmation('');
      setNotice(`Applied ${result.files.length} file change(s). A backup was created. Build and test the project before using the changes.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not apply the approved proposal.');
    } finally {
      setBusy(false);
    }
  };

  const rollback = async () => {
    if (!proposal || proposal.status !== 'applied') return;
    const phrase = `RESTORE:${proposal.id}`;
    if (confirmation !== phrase) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.rollbackSelfDevelopment(proposal.id, confirmation);
      setProposal({ ...proposal, status: 'rolled_back' });
      setConfirmation('');
      setNotice(`Restored ${result.files.length} file(s) from the automatic backup.`);
      await loadFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not roll back this proposal.');
    } finally {
      setBusy(false);
    }
  };

  return <div className="devlab-panel">
    <div className="devlab-title-row">
      <div><div className="eyebrow">SUPERVISED SELF-DEVELOPMENT</div><div className="chat-title">JARVIS Code Lab</div></div>
      <span className="devlab-lock"><ShieldCheck size={13}/> OPERATOR APPROVAL REQUIRED</span>
    </div>
    <p className="muted small">JARVIS can study selected source files, use your saved coding lessons, and propose code improvements through local Qwen. It cannot run a terminal, execute generated code, or approve its own changes.</p>

    <section className="devknowledge-section">
      <div className="devlab-field-label">LOCAL CODING NOTEBOOK · {knowledge.length} SAVED LESSON{knowledge.length === 1 ? '' : 'S'}</div>
      <p className="muted small">Teach JARVIS your architecture, preferred patterns, naming conventions, and lessons from bugs. These notes are supplied to future code proposals; they do not fine-tune Qwen.</p>
      <select className="devknowledge-category" value={knowledgeCategory} onChange={event => setKnowledgeCategory(event.target.value)}>
        <option value="project convention">PROJECT CONVENTION</option>
        <option value="architecture">ARCHITECTURE</option>
        <option value="bug lesson">BUG LESSON</option>
        <option value="code quality">CODE QUALITY</option>
        <option value="operator preference">YOUR CODING PREFERENCE</option>
      </select>
      <textarea className="devlab-goal devknowledge-input" value={knowledgeDraft} onChange={event => setKnowledgeDraft(event.target.value)} rows={2} maxLength={2000} placeholder="Example: Keep React components small, preserve existing behavior, use TypeScript types, and avoid adding dependencies." />
      <button className="small-primary devlab-generate" onClick={() => void saveKnowledge()} disabled={savingKnowledge || knowledgeDraft.trim().length < 8}>
        {savingKnowledge ? <><span className="mini-spinner"/> SAVING LESSON…</> : 'SAVE CODING LESSON'}
      </button>
      {knowledge.length > 0 && <div className="devknowledge-list">{knowledge.map(item => <article className="devknowledge-item" key={item.id}>
        <div><span>{item.category.toUpperCase()}</span><button className="devknowledge-delete" onClick={() => void removeKnowledge(item)} aria-label={`Delete ${item.category} lesson`}>REMOVE</button></div>
        <p>{item.content}</p>
      </article>)}</div>}
    </section>

    <label className="devlab-field-label" htmlFor="dev-goal">IMPROVEMENT REQUEST</label>
    <textarea id="dev-goal" className="devlab-goal" value={goal} onChange={event => setGoal(event.target.value)} rows={3} maxLength={1600} placeholder="Describe one focused code improvement…" />

    <div className="devlab-field-label">SOURCE FILES · SELECT UP TO TWO FROM THE SAFE ALLOWLIST</div>
    <div className="devlab-files">
      {files.map(file => <label className="devlab-file" key={file.path}>
        <input type="checkbox" checked={selected.includes(file.path)} onChange={() => toggleFile(file.path)} disabled={!selected.includes(file.path) && selected.length >= 2}/>
        <span><b>{file.path}</b><small>{file.description} · {file.size.toLocaleString()} chars</small></span>
      </label>)}
    </div>
    <button className="small-primary devlab-generate" onClick={() => void createProposal()} disabled={busy || goal.trim().length < 8 || selected.length < 1}>
      {busy ? <><span className="mini-spinner"/> GENERATING PROPOSAL…</> : <><Sparkles size={14}/> ASK LOCAL QWEN TO IMPROVE IT</>}
    </button>

    {error && <div className="inline-error">{error}</div>}
    {notice && <div className="inline-notice">{notice}</div>}

    {proposal && <section className="devlab-proposal">
      <div className="devlab-proposal-head"><span><Code2 size={14}/> PROPOSAL · {proposal.status.toUpperCase()}</span><small>{proposal.id}</small></div>
      <h3>{proposal.summary}</h3>
      {proposal.warnings.length > 0 && <div className="devlab-warning"><AlertTriangle size={14}/><div>{proposal.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</div></div>}
      {proposal.changes.map(change => <details className="devlab-diff" key={change.path} open>
        <summary><FileCode2 size={13}/><b>{change.path}</b><span>{change.reason}</span></summary>
        <pre>{change.diff || '(No textual difference returned)'}</pre>
      </details>)}
      {proposal.status === 'pending' && <div className="devlab-approval">
        <p>Review the complete diff. To apply it, type this exact phrase:</p>
        <code>{proposal.confirmation_required}</code>
        <input value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Type the approval phrase exactly" spellCheck={false}/>
        <button className="small-primary" onClick={() => void applyProposal()} disabled={busy || confirmation !== proposal.confirmation_required}><CheckCircle2 size={13}/> APPROVE & APPLY</button>
      </div>}
      {proposal.status === 'applied' && <div className="devlab-approval">
        <p>Changes are applied and backed up. Test them before continuing. To restore the backup, type:</p>
        <code>RESTORE:{proposal.id}</code>
        <input value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Type the rollback phrase exactly" spellCheck={false}/>
        <button className="stop-speech-btn" onClick={() => void rollback()} disabled={busy || confirmation !== `RESTORE:${proposal.id}`}><RotateCcw size={13}/> ROLL BACK CHANGES</button>
      </div>}
      {proposal.status === 'rolled_back' && <div className="inline-notice">The original files have been restored.</div>}
    </section>}

    <div className="devlab-protocol-note"><ShieldCheck size={15}/><span><b>Protected and locked:</b> authentication, local API token checks, filesystem allowlists, network policy, startup scripts, voice listener, image worker, and this approval system. JARVIS cannot modify these files through this lab.</span></div>
    <p className="devlab-footnote">Applying a proposal changes source files only. It does not automatically run them. You must build and test the project, and every application creates a restorable backup under F:\JARVIS\data\self_development. Core API/authentication, filesystem/network policy, voice routing, image worker, app approval UI and self-development enforcement remain locked.</p>
  </div>;
}
