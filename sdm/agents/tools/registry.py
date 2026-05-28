from langchain_core.tools import BaseTool

from .project.coordination import (
    build_search_communications,
    build_search_decisions,
)
from .project.executor import ProjectFactToolExecutor
from .project.finance import build_calculate_delay_cost, build_get_budget, build_get_resource_rates
from .project.overview import build_get_problem_context, build_get_project_summary
from .project.planning import (
    build_get_critical_tasks,
    build_get_task_dependency_graph,
    build_search_dependencies,
    build_search_tasks,
)
from .project.risks import build_search_risks
from .retrieval.executor import ProjectEvidenceExecutor
from .retrieval.tools import build_get_evidence_context, build_search_project_evidence


def build_project_tools(
    fact_executor: ProjectFactToolExecutor, evidence_executor: ProjectEvidenceExecutor
) -> list[BaseTool]:
    """Собирает инструменты проекта в порядке, доступном модели."""
    return [
        build_get_evidence_context(evidence_executor),
        build_get_project_summary(fact_executor),
        build_get_problem_context(fact_executor),
        build_get_critical_tasks(fact_executor),
        build_search_tasks(fact_executor),
        build_search_risks(fact_executor),
        build_search_communications(fact_executor),
        build_search_decisions(fact_executor),
        build_search_dependencies(fact_executor),
        build_search_project_evidence(evidence_executor),
        build_get_budget(fact_executor),
        build_get_resource_rates(fact_executor),
        build_get_task_dependency_graph(fact_executor),
        build_calculate_delay_cost(fact_executor),
    ]
