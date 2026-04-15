from synapse.communication.policies.reply_style import render_reply
from synapse.protocol import TaskSummary


def test_reply_style_avoids_mechanical_success_text():
    reply = render_reply("acknowledge_and_start", tool_results={})
    assert "successfully" not in reply.lower()
    assert "task" not in reply.lower()


def test_reply_style_uses_summary_for_progress():
    summary = TaskSummary(task_id="task_1", conversational_summary="Still working on it.")
    reply = render_reply("inform_progress", tool_results={"query_task_summary": summary})
    assert reply == "Still working on it."
