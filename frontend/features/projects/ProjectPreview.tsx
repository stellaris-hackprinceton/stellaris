"use client";

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Artifact, Project } from "@/contracts/api";
import { api, artifactContentUrl } from "@/lib/api";
import { catalogApi, useCatalogFeatures } from "@/lib/catalog";
import styles from "./projects.module.css";

const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif", "image/avif"]);
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/ogg"]);

function useNearViewport(ref: RefObject<HTMLDivElement | null>) {
  const [near, setNear] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || near) return;
    if (typeof IntersectionObserver === "undefined") {
      const frame = window.requestAnimationFrame(() => setNear(true));
      return () => window.cancelAnimationFrame(frame);
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setNear(true); observer.disconnect(); }
    }, { rootMargin: "240px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [near, ref]);
  return near;
}

function usePreviewArtifact(projectId: string, kind: "chart" | "image" | "video", enabled: boolean) {
  const features = useCatalogFeatures();
  return useQuery({
    queryKey: ["project", projectId, "project-preview", kind, features.views ? "newest" : "saved"],
    queryFn: async ({ signal }) => {
      if (features.files && features.views) {
        const file = (await catalogApi.files(projectId, { origin_type: "artifact", artifact_kinds: [kind], status: "active", sort: "created_at", order: "desc", limit: 1 }, signal)).data.items[0];
        return file?.project_id === projectId && file.origin?.type === "artifact"
          ? (await api.artifacts.get(projectId, file.origin.id, signal)).data : null;
      }
      // Older artifact lists are ascending. Keep requests bounded and label the preview as saved.
      return (await api.artifacts.list(projectId, { kind, limit: 1 }, signal)).data.items[0] ?? null;
    },
    enabled: enabled && !features.is_loading,
    retry: false,
    staleTime: 60_000,
  });
}

function mediaType(artifact: Artifact | null | undefined) {
  return artifact?.mime_type.toLowerCase().split(";")[0].trim() ?? "";
}

export function ProjectPreview({ project }: { project: Project }) {
  const frame = useRef<HTMLDivElement>(null);
  const near = useNearViewport(frame);
  const chart = usePreviewArtifact(project.id, "chart", near);
  const chartImage = chart.data?.project_id === project.id && IMAGE_TYPES.has(mediaType(chart.data)) ? chart.data : null;
  const image = usePreviewArtifact(project.id, "image", near && chart.isFetched && !chartImage);
  const imageArtifact = image.data?.project_id === project.id && image.data.origin === "observed" && image.data.experiment_id !== null && IMAGE_TYPES.has(mediaType(image.data)) ? image.data : null;
  const video = usePreviewArtifact(project.id, "video", near && chart.isFetched && !chartImage && image.isFetched && !imageArtifact);
  const videoArtifact = video.data?.project_id === project.id && video.data.origin === "observed" && video.data.experiment_id !== null && VIDEO_TYPES.has(mediaType(video.data)) ? video.data : null;
  const artifact = chartImage ?? imageArtifact ?? videoArtifact;
  const [failedId, setFailedId] = useState<string | null>(null);
  const visibleArtifact = artifact?.id === failedId ? null : artifact;
  const question = project.research_question?.trim() || project.description?.trim() || "No research question yet";

  return (
    <div className={styles.preview} ref={frame} data-has-media={visibleArtifact ? "true" : "false"}>
      {visibleArtifact && IMAGE_TYPES.has(mediaType(visibleArtifact)) ? (
        // eslint-disable-next-line @next/next/no-img-element -- Project-scoped content requires same-origin session cookies.
        <img className={`${styles.previewMedia} ${visibleArtifact.kind === "chart" ? styles.previewChart : ""}`} src={artifactContentUrl(project.id, visibleArtifact.id, "inline")} alt={visibleArtifact.filename} loading="lazy" onError={() => setFailedId(visibleArtifact.id)} />
      ) : visibleArtifact ? (
        <video className={styles.previewMedia} src={artifactContentUrl(project.id, visibleArtifact.id, "inline")} aria-label={visibleArtifact.filename} muted playsInline preload="metadata" onError={() => setFailedId(visibleArtifact.id)} />
      ) : (
        <span className={styles.questionPreview}>{question}</span>
      )}
      {visibleArtifact && <span className={styles.originLabel}>{visibleArtifact.kind === "chart" ? "Saved chart" : visibleArtifact.kind === "video" ? "Recording" : "Image"} · {visibleArtifact.origin}</span>}
    </div>
  );
}
