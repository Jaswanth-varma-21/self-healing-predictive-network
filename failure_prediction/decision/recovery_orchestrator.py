import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _path in (_PROJECT_ROOT, _PROJECT_ROOT / "digital_twin"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from security.trust_layer import safe_recovery_gate
from failure_prediction.decision.recovery_recommendation import (
    build_recovery_recommendation,
)
from failure_prediction.decision.counterfactual_recovery_decision import (
    build_counterfactual_recovery_decision,
)
from failure_prediction.decision.recovery_path import (
    DEFAULT_SOURCE,
    DEFAULT_DESTINATION,
    get_primary_link,
)
from failure_prediction.decision.recovery_storage import (
    store_recovery_decision,
)

from state.network_state import create_initial_network_state
from counterfactual.scenario import create_counterfactual_scenario
from counterfactual.engine import simulate_counterfactual
from counterfactual.outcome_evaluator import evaluate_counterfactual_outcome


def orchestrate_recovery(prediction_result, causal_result, source="h1"):
    """Build, counterfactually validate, and persist a recovery decision."""

    recommendation = build_recovery_recommendation(
        prediction_result,
        causal_result,
    )

    if recommendation["recovery_action"] in {
        "REROUTE_TRAFFIC",
        "INCREASE_MONITORING",
    }:
        primary_link = get_primary_link(source)
        network_state = create_initial_network_state()

        scenario = create_counterfactual_scenario(
            scenario_id="RECOVERY-CF-001",
            action="LINK_FAILURE",
            source=primary_link["source"],
            destination=primary_link["destination"],
            status="down",
            description=(
                "Simulate failure of the current primary link "
                "to evaluate connectivity and recovery feasibility."
            ),
        )

        counterfactual_state = simulate_counterfactual(
            network_state,
            scenario,
        )

        outcome = evaluate_counterfactual_outcome(
            counterfactual_state,
            scenario,
            DEFAULT_SOURCE,
            DEFAULT_DESTINATION,
        )
    else:
        outcome = {
            "scenario_id": "RECOVERY-CF-NONE",
            "action": "NO_SIMULATION",
            "source": DEFAULT_SOURCE,
            "destination": DEFAULT_DESTINATION,
            "reachable": True,
            "path_status": "not_simulated",
            "network_status": "not_simulated",
            "links_operational": None,
            "links_total": None,
        }

    final_decision = build_counterfactual_recovery_decision(
        recommendation,
        outcome,
    )

    gate_approved, gate_reason = safe_recovery_gate(
        final_decision,
        role="controller",
        context={"source": source, "stage": "recovery_orchestrator"},
    )
    if not gate_approved:
        final_decision = {
            **final_decision,
            "recovery_decision": "SAFE_FALLBACK",
            "recovery_action": "NONE",
            "action_description": f"Security gate rejected action: {gate_reason}",
            "security_gate_approved": False,
            "security_gate_reason": gate_reason,
        }
    else:
        final_decision = {
            **final_decision,
            "security_gate_approved": True,
            "security_gate_reason": gate_reason,
        }

    decision_id = store_recovery_decision(
        source="recovery_orchestrator",
        node=source,
        recommendation=final_decision,
    )

    return {
        **final_decision,
        "counterfactual_outcome": outcome,
        "recovery_decision_id": decision_id,
    }


if __name__ == "__main__":
    print("RECOVERY_ORCHESTRATOR_MODULE: CREATED")
