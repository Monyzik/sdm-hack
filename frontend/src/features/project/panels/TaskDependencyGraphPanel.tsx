import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type {
  ProblemTaskFact,
  ProjectProblemContext,
  TaskDependencyGraphEdge,
} from "../../../api/types";
import { Badge, EmptyState, LoadingState, Panel } from "../../../components/ui";
import { formatDate, formatDays } from "../../../lib/format";
import { severityTone, statusLabel } from "../../../lib/risk";

interface TaskDependencyGraphPanelProps {
  context: ProjectProblemContext | undefined;
  isLoading: boolean;
  errorMessage: string | null;
}

interface GraphNode {
  id: string;
  title: string;
  shortTitle: string;
  status?: string;
  priority?: string;
  plannedDueDate?: string;
  assigneeName?: string;
  estimatedHours?: number;
  spentHours?: number;
  overdueDays?: number;
  blockerReason?: string | null;
}

interface CriticalTreePage {
  id: string;
  rootId: string;
  nodeIds: string[];
  edgeIds: string[];
}

interface CriticalGraph {
  nodesById: Map<string, GraphNode>;
  childrenById: Map<string, string[]>;
  edgeByPair: Map<string, TaskDependencyGraphEdge>;
  trees: CriticalTreePage[];
}

export function TaskDependencyGraphPanel({
  context,
  isLoading,
  errorMessage,
}: TaskDependencyGraphPanelProps) {
  const [activeTreeIndex, setActiveTreeIndex] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const criticalEdges = useMemo(
    () =>
      (context?.task_dependency_graph ?? []).filter(
        (edge) => edge.is_critical_path,
      ),
    [context],
  );
  const graph = useMemo(
    () => buildCriticalGraph(criticalEdges, context?.problem_tasks ?? []),
    [criticalEdges, context],
  );
  const activeTree = graph.trees[activeTreeIndex] ?? graph.trees[0];
  const selectedNode = graph.nodesById.get(selectedNodeId ?? "");

  useEffect(() => {
    setActiveTreeIndex(0);
    setSelectedNodeId(null);
  }, [context?.as_of_date]);

  useEffect(() => {
    if (activeTreeIndex >= graph.trees.length) {
      setActiveTreeIndex(Math.max(0, graph.trees.length - 1));
    }
  }, [activeTreeIndex, graph.trees.length]);

  return (
    <Panel
      title="Граф критических зависимостей"
      icon={<GitBranch className="size-4" />}
    >
      {isLoading ? <LoadingState label="Загрузка графа…" /> : null}
      {!isLoading && errorMessage ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
          {errorMessage}
        </div>
      ) : null}
      {!isLoading && !errorMessage && criticalEdges.length === 0 ? (
        <EmptyState message="Критических зависимостей задач нет" />
      ) : null}
      {!isLoading && !errorMessage && activeTree ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
            <div>
              <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Дерево {activeTreeIndex + 1} из {graph.trees.length}
              </div>
              <div className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                Корень: {activeTree.rootId} · {activeTree.nodeIds.length} задач
              </div>
            </div>
            <div className="inline-flex items-center gap-1">
              <button
                type="button"
                disabled={activeTreeIndex === 0}
                onClick={() => {
                  setActiveTreeIndex((value) => Math.max(0, value - 1));
                  setSelectedNodeId(null);
                }}
                className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <ChevronLeft aria-hidden className="size-4" />
                <span className="sr-only">Предыдущее дерево</span>
              </button>
              <button
                type="button"
                disabled={activeTreeIndex >= graph.trees.length - 1}
                onClick={() => {
                  setActiveTreeIndex((value) =>
                    Math.min(graph.trees.length - 1, value + 1),
                  );
                  setSelectedNodeId(null);
                }}
                className="grid size-8 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <ChevronRight aria-hidden className="size-4" />
                <span className="sr-only">Следующее дерево</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="min-w-[720px]">
              <TreeNode
                nodeId={activeTree.rootId}
                graph={graph}
                onSelect={setSelectedNodeId}
                visited={new Set()}
              />
            </div>
          </div>

          {selectedNode ? (
            <TaskDetailsModal
              node={selectedNode}
              onClose={() => setSelectedNodeId(null)}
            />
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}

function TreeNode({
  nodeId,
  graph,
  onSelect,
  visited,
}: {
  nodeId: string;
  graph: CriticalGraph;
  onSelect: (nodeId: string) => void;
  visited: Set<string>;
}) {
  const node = graph.nodesById.get(nodeId);
  if (!node || visited.has(nodeId)) return null;

  const nextVisited = new Set(visited);
  nextVisited.add(nodeId);
  const children = graph.childrenById.get(nodeId) ?? [];

  return (
    <div className="flex items-start gap-4">
      <GraphNodeButton node={node} onSelect={() => onSelect(node.id)} />

      {children.length ? (
        <div className="relative flex flex-col gap-3 border-l border-slate-300 pl-6 dark:border-slate-700">
          {children.map((childId) => {
            const edge = graph.edgeByPair.get(edgeKey(nodeId, childId));
            return (
              <div key={`${nodeId}-${childId}`} className="relative">
                <div className="absolute -left-6 top-8 h-px w-5 bg-slate-300 dark:bg-slate-700" />
                {edge?.lag_days ? (
                  <div className="absolute -left-3 top-1 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    +{edge.lag_days}д
                  </div>
                ) : null}
                <TreeNode
                  nodeId={childId}
                  graph={graph}
                  onSelect={onSelect}
                  visited={nextVisited}
                />
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function GraphNodeButton({
  node,
  onSelect,
}: {
  node: GraphNode;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      title={nodeTooltip(node)}
      className={[
        "group min-h-20 w-56 shrink-0 rounded-lg border px-3 py-2 text-left shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400",
        node.status === "blocked"
          ? "border-rose-200 bg-rose-50 text-slate-950 hover:border-rose-300 dark:border-rose-900/70 dark:bg-rose-950/20 dark:text-slate-50"
          : "border-slate-200 bg-white text-slate-950 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-50",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
          {node.id}
        </span>
        {node.status === "blocked" ? (
          <AlertTriangle
            aria-hidden
            className="size-4 shrink-0 text-rose-500"
          />
        ) : null}
      </div>
      <div className="mt-1 line-clamp-2 text-sm font-semibold leading-5">
        {node.shortTitle}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {node.priority ? (
          <Badge tone={severityTone(node.priority)}>
            {statusLabel(node.priority)}
          </Badge>
        ) : null}
        {node.overdueDays ? (
          <Badge tone="warning">{formatDays(node.overdueDays)}</Badge>
        ) : null}
      </div>
    </button>
  );
}

function TaskDetailsModal({
  node,
  onClose,
}: {
  node: GraphNode;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-800 dark:bg-slate-950"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
              Задача {node.id}
            </div>
            <h4 className="mt-1 text-lg font-semibold leading-6 text-slate-950 dark:text-slate-50">
              {node.title}
            </h4>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-900"
          >
            <X aria-hidden className="size-4" />
            <span className="sr-only">Закрыть</span>
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {node.priority ? (
            <Badge tone={severityTone(node.priority)}>
              {statusLabel(node.priority)}
            </Badge>
          ) : null}
          {node.status ? (
            <Badge tone={severityTone(node.status)}>
              {statusLabel(node.status)}
            </Badge>
          ) : null}
          {node.overdueDays ? (
            <Badge tone="warning">{formatDays(node.overdueDays)}</Badge>
          ) : null}
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          <DetailItem label="Исполнитель" value={node.assigneeName ?? "нет данных"} />
          <DetailItem
            label="Плановый срок"
            value={node.plannedDueDate ? formatDate(node.plannedDueDate) : "нет данных"}
          />
          <DetailItem
            label="Трудозатраты"
            value={
              node.estimatedHours !== undefined && node.spentHours !== undefined
                ? `${node.spentHours} / ${node.estimatedHours} ч`
                : "нет данных"
            }
          />
        </div>

        {node.blockerReason ? (
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700 dark:bg-slate-900 dark:text-slate-300">
            <span className="font-semibold text-slate-950 dark:text-slate-50">
              Блокер:
            </span>{" "}
            {node.blockerReason}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white px-3 py-2 dark:bg-slate-900">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

function buildCriticalGraph(
  edges: TaskDependencyGraphEdge[],
  problemTasks: ProblemTaskFact[],
): CriticalGraph {
  const problemById = new Map(problemTasks.map((task) => [task.id, task]));
  const nodesById = new Map<string, GraphNode>();
  const incomingByNode = new Map<string, string[]>();
  const childrenById = new Map<string, string[]>();
  const edgeByPair = new Map<string, TaskDependencyGraphEdge>();

  for (const edge of edges) {
    ensureNode(nodesById, problemById, edge.depends_on_task_id, edge.depends_on_task_title);
    ensureNode(nodesById, problemById, edge.task_id, edge.task_title);

    appendUnique(childrenById, edge.depends_on_task_id, edge.task_id);
    appendUnique(incomingByNode, edge.task_id, edge.depends_on_task_id);
    edgeByPair.set(edgeKey(edge.depends_on_task_id, edge.task_id), edge);
  }

  for (const [nodeId, children] of childrenById) {
    childrenById.set(
      nodeId,
      children.sort((left, right) => compareNodes(nodesById, left, right)),
    );
  }

  const rootIds = [...nodesById.keys()]
    .filter((nodeId) => (incomingByNode.get(nodeId)?.length ?? 0) === 0)
    .sort((left, right) => compareNodes(nodesById, left, right));

  const trees = rootIds.map((rootId) =>
    buildTreePage(rootId, childrenById, edgeByPair),
  );

  return {
    nodesById,
    childrenById,
    edgeByPair,
    trees: trees.length
      ? trees.sort((left, right) => right.nodeIds.length - left.nodeIds.length || left.id.localeCompare(right.id))
      : edges.map((edge) => ({
          id: edge.id,
          rootId: edge.depends_on_task_id,
          nodeIds: [edge.depends_on_task_id, edge.task_id],
          edgeIds: [edge.id],
        })),
  };
}

function buildTreePage(
  rootId: string,
  childrenById: Map<string, string[]>,
  edgeByPair: Map<string, TaskDependencyGraphEdge>,
): CriticalTreePage {
  const nodeIds: string[] = [];
  const edgeIds: string[] = [];
  const visited = new Set<string>();

  function walk(nodeId: string) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);
    nodeIds.push(nodeId);

    for (const childId of childrenById.get(nodeId) ?? []) {
      const edge = edgeByPair.get(edgeKey(nodeId, childId));
      if (edge) edgeIds.push(edge.id);
      walk(childId);
    }
  }

  walk(rootId);

  return {
    id: `${rootId}-${edgeIds.join("-")}`,
    rootId,
    nodeIds,
    edgeIds,
  };
}

function ensureNode(
  nodesById: Map<string, GraphNode>,
  problemById: Map<string, ProblemTaskFact>,
  id: string,
  title: string,
) {
  if (nodesById.has(id)) return;
  const problemTask = problemById.get(id);
  nodesById.set(id, {
    id,
    title,
    shortTitle: shortTaskTitle(title),
    status: normalizeStatus(problemTask?.status),
    priority: normalizeStatus(problemTask?.priority),
    plannedDueDate: problemTask?.planned_due_date,
    assigneeName: problemTask?.assignee_name,
    estimatedHours: problemTask?.estimated_hours,
    spentHours: problemTask?.spent_hours,
    overdueDays: problemTask?.overdue_days,
    blockerReason: problemTask?.blocker_reason,
  });
}

function appendUnique(map: Map<string, string[]>, key: string, value: string) {
  const values = map.get(key) ?? [];
  if (!values.includes(value)) {
    map.set(key, [...values, value]);
  }
}

function compareNodes(
  nodesById: Map<string, GraphNode>,
  leftId: string,
  rightId: string,
) {
  const left = nodesById.get(leftId);
  const right = nodesById.get(rightId);
  const leftSeverity = nodeSeverity(left);
  const rightSeverity = nodeSeverity(right);
  return rightSeverity - leftSeverity || leftId.localeCompare(rightId);
}

function nodeSeverity(node: GraphNode | undefined) {
  if (!node) return 0;
  return (
    (node.status === "blocked" ? 100 : 0) +
    (node.priority === "critical" ? 50 : node.priority === "high" ? 25 : 0) +
    (node.overdueDays ?? 0)
  );
}

function edgeKey(fromId: string, toId: string) {
  return `${fromId}->${toId}`;
}

function normalizeStatus(value: string | undefined) {
  return value?.trim().toLowerCase().replace(/\s+/g, "_");
}

function shortTaskTitle(value: string) {
  return value.length > 42 ? `${value.slice(0, 39).trim()}...` : value;
}

function nodeTooltip(node: GraphNode) {
  const parts = [
    node.title,
    node.status ? `Статус: ${statusLabel(node.status)}` : null,
    node.priority ? `Приоритет: ${statusLabel(node.priority)}` : null,
    node.overdueDays ? `Просрочка: ${formatDays(node.overdueDays)}` : null,
  ].filter(Boolean);
  return parts.join("\n");
}
