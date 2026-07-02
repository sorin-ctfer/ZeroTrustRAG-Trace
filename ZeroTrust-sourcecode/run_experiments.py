from __future__ import annotations

import json
from agent_demo_app.experiments import PipelineRunner

if __name__ == "__main__":
    summary = PipelineRunner().run_all(graph_task_limit=12)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
