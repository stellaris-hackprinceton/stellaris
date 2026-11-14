"use client";
import { useMemo } from "react";
import type { Artifact, Claim, ID } from "@/contracts/api";
import { useArtifacts, useClaims } from "@/lib/queries";

/** ID → record maps over already-loaded pages. A miss means "not loaded or unavailable", never "fake it". */
export function useClaimMap(project_id: ID): Map<ID, Claim> {
  const claims = useClaims(project_id, {});
  return useMemo(() => new Map(claims.items.map((c) => [c.id, c])), [claims.items]);
}

export function useArtifactMap(project_id: ID): Map<ID, Artifact> {
  const artifacts = useArtifacts(project_id, {});
  return useMemo(() => new Map(artifacts.items.map((a) => [a.id, a])), [artifacts.items]);
}
