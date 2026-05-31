import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import Settings
from app.domain.models import (
    CallServiceNode,
    ExitNode,
    IfEqualsNode,
    IfFileExistsNode,
    Node,
    PrintNode,
    ReadFileNode,
    SetVariableNode,
    WorkflowDefinition,
    WorkflowError,
)
from app.domain.validation import ValidationResult

logger = logging.getLogger(__name__)

LINEAR_ACTIONS = {"set_variable", "call_service", "read_file", "print"}
BRANCH_ACTIONS = {"if_equals", "if_file_exists"}


@dataclass
class WorkflowValidator:
    """Validates workflow graph structure, routing rules, and call_service limits."""

    settings: Settings

    def validate(self, workflow: WorkflowDefinition) -> ValidationResult:
        """Run all structural checks against a workflow definition.

        Args:
            workflow: Workflow graph submitted for execution.

        Returns:
            ValidationResult: ``ok=True`` when no errors were found.
        """
        errors: list[WorkflowError] = []

        # --- Schema and non-empty graph ---
        if workflow.schema_version != 1:
            errors.append(
                WorkflowError(
                    code="INVALID_SCHEMA_VERSION",
                    message=f"Unsupported schema_version {workflow.schema_version}; expected 1",
                )
            )

        if not workflow.nodes:
            errors.append(
                WorkflowError(
                    code="INVALID_WORKFLOW",
                    message="Workflow must contain at least one node",
                )
            )
            return ValidationResult.invalid(errors)

        # --- Index nodes and validate entry ---
        node_map: dict[str, Node] = {}
        for node in workflow.nodes:
            if node.id in node_map:
                errors.append(
                    WorkflowError(
                        code="DUPLICATE_NODE_ID",
                        message=f"Duplicate node id '{node.id}'",
                        step_id=node.id,
                    )
                )
            node_map[node.id] = node

        if workflow.entry not in node_map:
            errors.append(
                WorkflowError(
                    code="INVALID_ENTRY",
                    message=f"Entry node '{workflow.entry}' does not exist",
                )
            )

        # --- Per-node routing and action rules ---
        for node in workflow.nodes:
            errors.extend(self._validate_node(node, node_map))

        # --- Graph-level reachability and cycle checks ---
        if not errors:
            exit_error = self._validate_reachable_exit(workflow, node_map)
            if exit_error:
                errors.append(exit_error)

        if not errors:
            cycle_error = self._detect_cycle(workflow, node_map)
            if cycle_error:
                errors.append(cycle_error)

        if errors:
            return ValidationResult.invalid(errors)
        return ValidationResult.valid()

    def _validate_node(
        self, node: Node, node_map: dict[str, Node]
    ) -> list[WorkflowError]:
        """Validate routing fields and action-specific constraints for one node.

        Args:
            node: Node under validation.
            node_map: All workflow nodes keyed by id.

        Returns:
            list[WorkflowError]: Errors found for this node, possibly empty.
        """
        errors: list[WorkflowError] = []
        raw = self._node_routing_fields(node)

        has_next = raw["next"] is not None
        has_on_true = raw["on_true"] is not None
        has_on_false = raw["on_false"] is not None
        has_branch = has_on_true or has_on_false

        # --- Reject mixed linear and branch routing ---
        if has_next and has_branch:
            errors.append(
                WorkflowError(
                    code="INVALID_NODE_ROUTING",
                    message=(
                        f"Node '{node.id}' mixes linear routing (next) "
                        "with branch routing (on_true/on_false)"
                    ),
                    step_id=node.id,
                    action=node.action,
                )
            )
            return errors

        # --- Exit nodes must not route further ---
        if isinstance(node, ExitNode):
            if has_next or has_on_true or has_on_false:
                errors.append(
                    WorkflowError(
                        code="INVALID_NODE_ROUTING",
                        message=f"Exit node '{node.id}' must not have routing fields",
                        step_id=node.id,
                        action="exit",
                    )
                )
            return errors

        # --- Linear action routing ---
        if node.action in LINEAR_ACTIONS:
            if not has_next:
                errors.append(
                    WorkflowError(
                        code="INVALID_NODE_ROUTING",
                        message=f"Linear node '{node.id}' requires 'next'",
                        step_id=node.id,
                        action=node.action,
                    )
                )
            elif has_on_true or has_on_false:
                errors.append(
                    WorkflowError(
                        code="INVALID_NODE_ROUTING",
                        message=(
                            f"Linear node '{node.id}' must not have "
                            "on_true/on_false"
                        ),
                        step_id=node.id,
                        action=node.action,
                    )
                )
            else:
                errors.extend(
                    self._validate_ref(node.next, node.id, node_map)  # type: ignore[attr-defined]
                )

        # --- Branch action routing ---
        if node.action in BRANCH_ACTIONS:
            if has_next:
                errors.append(
                    WorkflowError(
                        code="INVALID_NODE_ROUTING",
                        message=f"Branch node '{node.id}' must not have 'next'",
                        step_id=node.id,
                        action=node.action,
                    )
                )
            elif not has_on_true or not has_on_false:
                errors.append(
                    WorkflowError(
                        code="INVALID_NODE_ROUTING",
                        message=(
                            f"Branch node '{node.id}' requires both "
                            "on_true and on_false"
                        ),
                        step_id=node.id,
                        action=node.action,
                    )
                )
            else:
                branch_node = node  # type: ignore[assignment]
                errors.extend(
                    self._validate_ref(branch_node.on_true, node.id, node_map)
                )
                errors.extend(
                    self._validate_ref(branch_node.on_false, node.id, node_map)
                )

        # --- Action-specific constraints ---
        if isinstance(node, PrintNode) and not node.parts:
            errors.append(
                WorkflowError(
                    code="INVALID_PRINT_PARTS",
                    message=f"Print node '{node.id}' requires non-empty parts",
                    step_id=node.id,
                    action="print",
                )
            )

        if isinstance(node, CallServiceNode):
            errors.extend(self._validate_call_service(node))

        return errors

    def _validate_call_service(self, node: CallServiceNode) -> list[WorkflowError]:
        """Validate URL scheme and call_service timeout/retry limits.

        Args:
            node: call_service node under validation.

        Returns:
            list[WorkflowError]: Errors for invalid URL or exceeded limits.
        """
        errors: list[WorkflowError] = []

        # --- URL must be http(s) with a host ---
        parsed = urlparse(node.url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors.append(
                WorkflowError(
                    code="CALL_SERVICE_URL_NOT_ALLOWED",
                    message="URL must be http(s) with a valid host",
                    step_id=node.id,
                    action="call_service",
                )
            )

        # --- Per-node limits must not exceed configured caps ---
        if node.timeout_seconds is not None:
            if node.timeout_seconds > self.settings.call_service_max_timeout_seconds:
                errors.append(
                    WorkflowError(
                        code="CALL_SERVICE_TIMEOUT_TOO_LARGE",
                        message=(
                            f"timeout_seconds {node.timeout_seconds} exceeds max "
                            f"{self.settings.call_service_max_timeout_seconds}"
                        ),
                        step_id=node.id,
                        action="call_service",
                    )
                )

        if node.max_retries is not None:
            if node.max_retries > self.settings.call_service_max_retries_cap:
                errors.append(
                    WorkflowError(
                        code="CALL_SERVICE_RETRIES_TOO_LARGE",
                        message=(
                            f"max_retries {node.max_retries} exceeds cap "
                            f"{self.settings.call_service_max_retries_cap}"
                        ),
                        step_id=node.id,
                        action="call_service",
                    )
                )

        return errors

    def _validate_ref(
        self, ref: str, node_id: str, node_map: dict[str, Node]
    ) -> list[WorkflowError]:
        """Ensure a routing reference points to an existing node id.

        Args:
            ref: Target node id from ``next``, ``on_true``, or ``on_false``.
            node_id: Source node id for error reporting.
            node_map: All workflow nodes keyed by id.

        Returns:
            list[WorkflowError]: Single error when ``ref`` is unknown, else empty.
        """
        if ref not in node_map:
            return [
                WorkflowError(
                    code="INVALID_NODE_REFERENCE",
                    message=f"Node '{node_id}' references unknown node '{ref}'",
                    step_id=node_id,
                )
            ]
        return []

    def _node_routing_fields(self, node: Node) -> dict:
        """Extract routing field values normalized across node types.

        Args:
            node: Workflow node whose routing fields are inspected.

        Returns:
            dict: Keys ``next``, ``on_true``, and ``on_false`` with values or None.
        """
        if isinstance(node, ExitNode):
            return {"next": None, "on_true": None, "on_false": None}
        if isinstance(node, (IfEqualsNode, IfFileExistsNode)):
            return {
                "next": node.next,
                "on_true": node.on_true,
                "on_false": node.on_false,
            }
        return {
            "next": node.next,
            "on_true": node.on_true,
            "on_false": node.on_false,
        }

    def _outgoing(self, node: Node) -> list[str]:
        """Return successor node ids for graph traversal.

        Args:
            node: Node whose outgoing edges are needed.

        Returns:
            list[str]: Target node ids for linear or branch nodes; empty for exit.
        """
        if isinstance(node, ExitNode):
            return []
        if isinstance(node, (IfEqualsNode, IfFileExistsNode)):
            return [node.on_true, node.on_false]
        return [node.next]

    def _detect_cycle(
        self, workflow: WorkflowDefinition, node_map: dict[str, Node]
    ) -> WorkflowError | None:
        """Detect cycles in the workflow graph via DFS.

        Args:
            workflow: Workflow whose entry node starts traversal.
            node_map: All workflow nodes keyed by id.

        Returns:
            WorkflowError | None: Cycle error when found, otherwise None.
        """
        if workflow.entry not in node_map:
            return None

        visited: set[str] = set()
        stack: set[str] = set()

        def dfs(node_id: str) -> bool:
            """Depth-first search helper; returns True when a cycle is detected.

            Args:
                node_id: Current node id being visited.

            Returns:
                bool: True if ``node_id`` is re-entered on the active DFS stack.
            """
            if node_id in stack:
                return True
            if node_id in visited:
                return False
            visited.add(node_id)
            stack.add(node_id)
            node = node_map[node_id]
            for nxt in self._outgoing(node):
                if dfs(nxt):
                    return True
            stack.remove(node_id)
            return False

        if dfs(workflow.entry):
            return WorkflowError(
                code="CYCLE_DETECTED",
                message="Workflow graph contains a cycle",
            )
        return None

    def _validate_reachable_exit(
        self, workflow: WorkflowDefinition, node_map: dict[str, Node]
    ) -> WorkflowError | None:
        """Ensure at least one exit node is reachable from the entry node.

        Args:
            workflow: Workflow whose reachability is checked.
            node_map: All workflow nodes keyed by id.

        Returns:
            WorkflowError | None: Reachability error when no exit is reachable.
        """
        if workflow.entry not in node_map:
            return WorkflowError(
                code="NO_REACHABLE_EXIT",
                message="No exit node reachable from entry",
            )

        has_exit = any(isinstance(n, ExitNode) for n in workflow.nodes)
        if not has_exit:
            return WorkflowError(
                code="NO_REACHABLE_EXIT",
                message="Workflow must contain at least one exit node",
            )

        # --- Breadth-first search from entry ---
        visited: set[str] = set()
        queue = [workflow.entry]

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_map.get(node_id)
            if node is None:
                continue
            if isinstance(node, ExitNode):
                return None
            queue.extend(self._outgoing(node))

        return WorkflowError(
            code="NO_REACHABLE_EXIT",
            message="No exit node reachable from entry",
        )
