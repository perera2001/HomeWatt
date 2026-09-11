"""Rule-based supervisor for the HomeWatt workflow."""

from app.graph.state import HomeWattState


async def supervisor_node(state: HomeWattState) -> HomeWattState:
    """Prepare the first workflow version for the analyzer step."""
    return {
        **state,
        "is_valid": True,
    }
