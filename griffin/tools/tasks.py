"""Tasks — capability #2: "performing tasks for me," modeled as a to-do list
the assistant can add to, check off, and report on.
"""

import uuid
from datetime import datetime, timezone

from griffin.tools import storage
from griffin.tools.registry import Tool, ToolError

FILENAME = "tasks.json"


def _load():
    return storage.load(FILENAME, [])


def _save(tasks):
    storage.save(FILENAME, tasks)


def add_task(tool_input):
    text = (tool_input.get("text") or "").strip()
    if not text:
        raise ToolError("A task needs non-empty text.")

    tasks = _load()
    task = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "done": False,
    }
    tasks.append(task)
    _save(tasks)
    return f'Task added: "{text}" [id={task["id"]}]'


def list_tasks(tool_input):
    include_done = bool(tool_input.get("include_done", False))
    tasks = _load()
    if not include_done:
        tasks = [t for t in tasks if not t["done"]]
    if not tasks:
        return "No tasks." if include_done else "No open tasks."
    lines = [f'- [{t["id"]}] {t["text"]}' + (" (done)" if t["done"] else "") for t in tasks]
    return "\n".join(lines)


def complete_task(tool_input):
    task_id = (tool_input.get("id") or "").strip()
    tasks = _load()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            _save(tasks)
            return f'Marked task [{task_id}] as done: "{t["text"]}"'
    raise ToolError(f"No task found with id '{task_id}'.")


TOOLS = [
    Tool(
        name="add_task",
        description=(
            "Add something to the user's task list. Use this when they ask "
            "you to track or follow up on something concrete, e.g. 'add "
            "buy milk to my list' or 'I need to finish the report.'"
        ),
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The task to add."}},
            "required": ["text"],
        },
        handler=add_task,
    ),
    Tool(
        name="list_tasks",
        description=(
            "List the user's open tasks. Use this when they ask what's on "
            "their plate or what they still need to do."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "description": "Include completed tasks. Defaults to false.",
                },
            },
            "required": [],
        },
        handler=list_tasks,
    ),
    Tool(
        name="complete_task",
        description="Mark a task as done, given its id. Use when the user says they've finished something.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The task's id."}},
            "required": ["id"],
        },
        handler=complete_task,
    ),
]
