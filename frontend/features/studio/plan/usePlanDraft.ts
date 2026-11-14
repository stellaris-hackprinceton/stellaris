"use client";
import { useCallback, useState } from "react";
import type { Experiment } from "@/contracts/api";
import { changedFields, toDraft } from "./draft";
import type { PlanDraft, PlanField } from "./draft";

type State = { experiment_id: string; base: PlanDraft; baseRevision: number; draft: PlanDraft };

/**
 * Local, unsaved plan edits for one experiment.
 * - `base` is the saved revision the draft started from; PATCH bodies are diffs against it.
 * - A newer saved revision replaces a clean draft automatically, but never a dirty one: then
 *   `remoteNewer` is true and the caller must reconcile (per field) and `rebase` before saving.
 * Uses "adjust state during render" instead of effects.
 */
export function usePlanDraft(experiment: Experiment | undefined) {
  const [state, setState] = useState<State | null>(() =>
    experiment ? { experiment_id: experiment.id, base: toDraft(experiment), baseRevision: experiment.revision, draft: toDraft(experiment) } : null);

  let s = state;
  if (experiment && (!s || s.experiment_id !== experiment.id)) {
    s = { experiment_id: experiment.id, base: toDraft(experiment), baseRevision: experiment.revision, draft: toDraft(experiment) };
    setState(s);
  } else if (experiment && s && experiment.revision > s.baseRevision && changedFields(s.base, s.draft).length === 0) {
    s = { ...s, base: toDraft(experiment), baseRevision: experiment.revision, draft: toDraft(experiment) };
    setState(s);
  }

  const setDraft = useCallback((fn: (d: PlanDraft) => PlanDraft) => {
    setState((prev) => (prev ? { ...prev, draft: fn(prev.draft) } : prev));
  }, []);

  const saved = experiment ? toDraft(experiment) : null;
  const dirtyFields = s ? changedFields(s.base, s.draft) : [];
  const remoteNewer = Boolean(experiment && s && experiment.revision > s.baseRevision);
  // Fields changed both locally and remotely since `base`: the ones that need a decision.
  const conflicting: PlanField[] = remoteNewer && s && saved
    ? changedFields(s.base, saved).filter((f) => dirtyFields.includes(f))
    : [];

  return {
    draft: s?.draft ?? null,
    base: s?.base ?? null,
    baseRevision: s?.baseRevision ?? null,
    saved,
    dirty: dirtyFields.length > 0,
    dirtyFields,
    remoteNewer,
    conflicting,
    setDraft,
    /** Take the saved value for one field. */
    useSaved(field: PlanField) {
      if (!saved) return;
      setDraft((d) => ({ ...d, [field]: structuredClone(saved[field]) }));
    },
    /**
     * Accept the newer saved revision as the new base, keeping local values for the fields the user
     * edited and taking saved values for everything else.
     */
    rebase() {
      if (!experiment || !saved) return;
      setState((prev) => {
        if (!prev) return prev;
        const mine = changedFields(prev.base, prev.draft);
        const merged = { ...saved };
        for (const f of mine) (merged as Record<string, unknown>)[f] = prev.draft[f];
        return { ...prev, base: saved, baseRevision: experiment.revision, draft: merged };
      });
    },
    discard() {
      if (!experiment) return;
      setState({ experiment_id: experiment.id, base: toDraft(experiment), baseRevision: experiment.revision, draft: toDraft(experiment) });
    },
    markSaved(x: Experiment) {
      setState({ experiment_id: x.id, base: toDraft(x), baseRevision: x.revision, draft: toDraft(x) });
    },
  };
}

export type PlanDraftController = ReturnType<typeof usePlanDraft>;
