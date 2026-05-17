"""Push coding-agent trajectories to a SWE Studio instance.

Example
-------

.. code-block:: python

    from swe_studio_sdk import attach

    with attach(run_id="my-aider-run", trajectory_id="issue-42") as ctx:
        ctx.user_message("Fix the off-by-one in foo.py")
        for thought, action, observation in agent_loop():
            ctx.step(thought=thought, action=action, observation=observation)
        ctx.finish(
            exit_status="submitted",
            submission=final_patch,
            eval="resolved",
            instance_cost=0.27,
            tokens_sent=18420,
            tokens_received=1923,
        )
"""

from .context import attach
from .client import StudioClient

__all__ = ["attach", "StudioClient"]
__version__ = "0.1.0"
