import { useEffect, useRef, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import type { CreateRunRequest, HealthResponse } from '../types';

interface NewRunDialogProps {
  open: boolean;
  health: HealthResponse | null;
  onClose: () => void;
  onCreate: (input: CreateRunRequest) => Promise<string>;
  onCreated: (id: string) => void;
}

export function NewRunDialog({ open, health, onClose, onCreate, onCreated }: NewRunDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [requirement, setRequirement] = useState('');
  const [projectId, setProjectId] = useState('');
  const [demoOutcome, setDemoOutcome] = useState<'ready' | 'blocked'>('ready');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const projects = health?.projects ?? [];

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  useEffect(() => {
    if (!projectId && projects.length) setProjectId(projects[0].id);
  }, [projectId, projects]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const cleanRequirement = requirement.trim();
    if (!cleanRequirement) {
      setError('Add a task requirement before continuing.');
      return;
    }
    if (!projectId) {
      setError('Choose a configured project.');
      return;
    }
    setSubmitting(true);
    try {
      const input: CreateRunRequest = {
        requirement: cleanRequirement,
        project_id: projectId,
        ...(health?.mode === 'demo' ? { demo_outcome: demoOutcome } : {}),
      };
      const id = await onCreate(input);
      setRequirement('');
      setError(null);
      onCreated(id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The task could not be created.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="factory-dialog new-run-dialog"
      aria-labelledby="new-run-title"
      onClose={onClose}
      onCancel={(event) => { if (submitting) event.preventDefault(); }}
    >
      <form onSubmit={submit}>
        <div className="dialog-heading">
          <h2 id="new-run-title">Start a task</h2>
          <button className="icon-button" type="button" onClick={() => dialog.current?.close()} disabled={submitting} aria-label="Close new task dialog">
            <X size={17} aria-hidden="true" />
          </button>
        </div>
        <p className="dialog-intro">Describe the requested change and choose its configured project.</p>
        <label className="field-label" htmlFor="run-requirement">Requirement</label>
        <textarea
          id="run-requirement"
          autoFocus
          required
          rows={5}
          maxLength={20000}
          value={requirement}
          disabled={submitting}
          onChange={(event) => setRequirement(event.target.value)}
          placeholder="What should the factory build or change?"
          aria-describedby="requirement-help"
        />
        <p id="requirement-help" className="field-help">Use concrete outcomes and acceptance criteria where possible. Maximum 20,000 characters.</p>
        <label className="field-label mt-4" htmlFor="run-project">Project</label>
        <select id="run-project" required value={projectId} onChange={(event) => setProjectId(event.target.value)} disabled={!projects.length || submitting}>
          {projects.length ? projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>) : <option value="">No configured projects available</option>}
        </select>
        {health?.mode === 'demo' && (
          <>
            <label className="field-label mt-4" htmlFor="demo-outcome">Demo outcome</label>
            <select id="demo-outcome" value={demoOutcome} onChange={(event) => setDemoOutcome(event.target.value as 'ready' | 'blocked')} disabled={submitting}>
              <option value="ready">Ready, including a repair round</option>
              <option value="blocked">Blocked with a finding</option>
            </select>
            <p className="field-help">Demo tasks use isolated synthetic events and do not modify a live run.</p>
          </>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button className="button-secondary" type="button" onClick={() => dialog.current?.close()} disabled={submitting}>Cancel</button>
          <button className="button-primary" type="submit" disabled={submitting || !projects.length || !health?.csrf_token}>
            {submitting ? 'Creating task…' : 'Create task'}
          </button>
        </div>
      </form>
    </dialog>
  );
}
