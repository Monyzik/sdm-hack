import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  FileText,
  FolderKanban,
  Loader2,
  Target,
  UploadCloud,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { ApiError, uploadProjectDocx } from "../../api/client";
import type {
  PortfolioProjectSummary,
  ProjectDocxUploadResult,
  ProjectKeyFields,
} from "../../api/types";
import { Card, EmptyState, LoadingState } from "../../components/ui";
import { useProjectProblemContext } from "../../hooks/useProjectProblemContext";
import { formatDate } from "../../lib/format";

interface ProjectDocumentUploadPageProps {
  projects: PortfolioProjectSummary[];
  selectedProjectId: string | null;
  asOfDate: string;
  onSelectProject: (projectId: string) => void;
}

export function ProjectDocumentUploadPage({
  projects,
  selectedProjectId,
  asOfDate,
  onSelectProject,
}: ProjectDocumentUploadPageProps) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [lastResult, setLastResult] = useState<ProjectDocxUploadResult | null>(
    null,
  );

  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId),
    [projects, selectedProjectId],
  );
  const contextQuery = useProjectProblemContext(
    selectedProjectId,
    asOfDate,
    2,
    Boolean(selectedProjectId),
  );

  const currentFields = contextQuery.data
    ? projectFactToKeyFields(contextQuery.data.project)
    : null;

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProjectId || !file) {
        throw new ApiError("Выберите проект и DOCX-файл.", 400);
      }
      return uploadProjectDocx(selectedProjectId, file, asOfDate);
    },
    onSuccess: (result) => {
      setLastResult(result);
      onSelectProject(result.project_id);
      void queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      void queryClient.invalidateQueries({ queryKey: ["portfolio-attention"] });
      void queryClient.invalidateQueries({
        queryKey: ["project", result.project_id],
      });
      void queryClient.invalidateQueries({
        queryKey: ["project-problem-context", result.project_id],
      });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const errorMessage = describeUploadError(uploadMutation.error);

  if (!projects.length) {
    return <EmptyState message="Проекты не загружены" />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
      <Card className="p-5">
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
                DOCX-паспорт
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {selectedProject?.project_name ?? "Проект не выбран"}
              </p>
            </div>
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
              <UploadCloud aria-hidden className="size-5" />
            </span>
          </div>

          <label
            htmlFor="docx-upload"
            className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-center transition hover:border-indigo-300 hover:bg-indigo-50/60 dark:border-slate-700 dark:bg-slate-950/40 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/20"
          >
            <FileText
              aria-hidden
              className="mb-3 size-8 text-slate-400 dark:text-slate-500"
            />
            <span className="max-w-full truncate text-sm font-medium text-slate-900 dark:text-slate-100">
              {file ? file.name : "Выберите DOCX"}
            </span>
            {file ? (
              <span className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {formatFileSize(file.size)}
              </span>
            ) : null}
          </label>
          <input
            id="docx-upload"
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="sr-only"
            onChange={(event) => {
              setLastResult(null);
              setFile(event.target.files?.[0] ?? null);
            }}
          />

          <button
            type="button"
            disabled={!selectedProjectId || !file || uploadMutation.isPending}
            onClick={() => uploadMutation.mutate()}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600 dark:disabled:bg-slate-800 dark:disabled:text-slate-500"
          >
            {uploadMutation.isPending ? (
              <Loader2 aria-hidden className="size-4 animate-spin" />
            ) : (
              <UploadCloud aria-hidden className="size-4" />
            )}
            Запустить пайплайн
          </button>

          {errorMessage ? (
            <div className="flex gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
              <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          ) : null}
        </div>
      </Card>

      <div className="flex min-w-0 flex-col gap-4">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
              Ключевые поля
            </h2>
            {contextQuery.isFetching ? (
              <Loader2
                aria-hidden
                className="size-4 animate-spin text-slate-400"
              />
            ) : null}
          </div>

          {contextQuery.isPending ? (
            <LoadingState label="Загрузка полей проекта…" />
          ) : currentFields ? (
            <KeyFieldsView fields={currentFields} />
          ) : (
            <EmptyState message="Нет данных по проекту" />
          )}
        </Card>

        {lastResult ? (
          <Card className="p-5">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950 dark:text-slate-50">
                  Результат загрузки
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {lastResult.original_file_name} {"->"}{" "}
                  {lastResult.stored_file_name}
                </p>
              </div>
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300">
                <CheckCircle2 aria-hidden className="size-5" />
              </span>
            </div>

            <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <ResultStat label="Проект" value={lastResult.project_id} />
              <ResultStat
                label="Событие"
                value={
                  lastResult.event_type === "docx_added"
                    ? "Добавлен DOCX"
                    : "Изменен DOCX"
                }
              />
              <ResultStat
                label="Алерты"
                value={lastResult.alerts_count.toString()}
              />
            </div>

            <KeyFieldsView fields={lastResult.updated_fields} />
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function KeyFieldsView({ fields }: { fields: ProjectKeyFields }) {
  return (
    <div className="grid grid-cols-1 gap-3">
      <FieldRow
        icon={<FolderKanban className="size-4" />}
        label="Имя проекта"
        value={fields.project_name}
      />
      <FieldRow
        icon={<CalendarDays className="size-4" />}
        label="Таймлайн"
        value={formatTimeline(fields.start_date, fields.planned_end_date)}
      />
      <FieldRow
        icon={<Target className="size-4" />}
        label="Цели"
        value={fields.business_goal}
        multiline
      />
      <FieldRow
        icon={<CheckCircle2 className="size-4" />}
        label="Результаты"
        value={fields.expected_result}
        multiline
      />
    </div>
  );
}

function FieldRow({
  icon,
  label,
  value,
  multiline = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  multiline?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        <span aria-hidden className="text-indigo-500 dark:text-indigo-300">
          {icon}
        </span>
        {label}
      </div>
      <div
        className={`text-sm leading-6 text-slate-900 dark:text-slate-100 ${
          multiline ? "whitespace-pre-line" : "truncate"
        }`}
      >
        {value || "Не заполнено"}
      </div>
    </div>
  );
}

function ResultStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-950/30">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-950 dark:text-slate-50">
        {value}
      </div>
    </div>
  );
}

function projectFactToKeyFields(project: {
  name: string;
  start_date: string;
  planned_end_date: string;
  business_goal: string;
  expected_result: string;
}): ProjectKeyFields {
  return {
    project_name: project.name,
    start_date: project.start_date,
    planned_end_date: project.planned_end_date,
    business_goal: project.business_goal,
    expected_result: project.expected_result,
  };
}

function formatTimeline(startDate: string | null, endDate: string | null) {
  if (!startDate && !endDate) return "Не заполнено";
  if (!startDate) return `до ${formatDate(endDate as string)}`;
  if (!endDate) return `с ${formatDate(startDate)}`;
  return `${formatDate(startDate)} - ${formatDate(endDate)}`;
}

function formatFileSize(size: number) {
  if (size < 1024 * 1024) {
    return `${Math.max(1, Math.round(size / 1024))} КБ`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} МБ`;
}

function describeUploadError(error: unknown): string | null {
  if (!error) return null;
  if (error instanceof ApiError) return error.message;
  return "Не удалось загрузить DOCX.";
}
