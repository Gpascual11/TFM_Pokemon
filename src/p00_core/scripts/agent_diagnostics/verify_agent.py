import sys
from pathlib import Path

# Ensure src/ is in the python path
SRC_DIR = Path(__file__).resolve().parents[4] / "src"
sys.path.insert(0, str(SRC_DIR))

from p01_heuristics.agents import get_agent_class


def test_agent_loading(agent_name):
    print(f"\nTesting: {agent_name}...")
    try:
        AgentClass = get_agent_class(agent_name)
        print(f"  Successfully loaded agent class: {AgentClass}")
        
        # Instantiate agent
        agent = AgentClass()
        print(f"  Successfully instantiated {agent_name}!")
        if hasattr(agent, "model"):
            print(f"  Trained model: {agent.model}")
        if agent_name == "ml_advanced" and hasattr(agent, "feature_columns"):
            print(f"  Feature columns length: {len(agent.feature_columns)}")
    except Exception:
        print(f"  FAILED to load or instantiate {agent_name}!")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_agent_loading("ml_baseline")
    test_agent_loading("ml_advanced")
    test_agent_loading("v15")
    test_agent_loading("v16")
    print("\nAll agents verified successfully!")
