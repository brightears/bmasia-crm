"""Activity log and change-proposal review queue.

Agents, jobs and people record customer interactions as ``Activity`` rows and
suggest record changes as ``ChangeProposal`` rows. A proposal changes nothing
until a person accepts it; accepting applies it through the guarded MCP write
path (``crm_app.mcp.update_record`` / ``create_record``) as the reviewer.

Both write surfaces are off until ``AGENT_ACTIVITY_WRITES_ENABLED`` and
``CHANGE_PROPOSALS_ENABLED`` are switched on. Nothing in this app sends email
or calls an external service.
"""
