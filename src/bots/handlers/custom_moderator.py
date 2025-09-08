"""
Custom moderator to prevent splitting of user questions into multiple queries.
"""

from __future__ import annotations

from typing import Optional, Dict
from collections import defaultdict

from botbuilder.core import TurnContext
from teams.ai.moderators.moderator import Moderator
from teams.ai.planners.plan import Plan, PredictedDoCommand
from teams.state import TurnState


class CustomModerator(Moderator):
    """
    Custom moderator that prevents splitting of user questions into multiple smaller queries.
    It ensures complex questions are processed as a single query regardless of action type.
    """

    async def review_input(self, context: TurnContext, state: TurnState) -> Optional[Plan]:
        # Return None to let the planner handle the query as a single unit
        # without attempting to split it into multiple questions
        return None

    async def review_output(self, context: TurnContext, state: TurnState, plan: Plan) -> Plan:
        # If there are multiple commands in the plan, keep only the first action command
        if len(plan.commands) > 1:
            first_action_command = None
            non_action_commands = []
            
            # Find the first action command and keep track of non-action commands
            for cmd in plan.commands:
                if hasattr(cmd, 'action') and first_action_command is None:
                    first_action_command = cmd
                elif not hasattr(cmd, 'action'):
                    non_action_commands.append(cmd)
            
            # Build new command list with just the first action command and any non-action commands
            simplified_commands = []
            if first_action_command:
                simplified_commands.append(first_action_command)
            simplified_commands.extend(non_action_commands)
            
            plan.commands = simplified_commands
            
        return plan