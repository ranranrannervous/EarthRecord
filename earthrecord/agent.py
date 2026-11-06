"""The agent used for every model: one system prompt, the same tools and limits, and a per-question submit tool."""

from inspect_ai.agent import AgentPrompt, AgentSubmit, as_solver, react
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.tool import bash, python, text_editor

from .tools import submit_tool, view_image

SYSTEM_PROMPT = (
    "You are analyzing satellite and climate data for a study area. All data are in /data (read-only); "
    "see /data/README.md for formats. You can run Python (packages are preinstalled) and write files under "
    "/work. There is no internet access. When finished, return your final answer as JSON following the "
    "provided schema."
)
CLOSED_BOOK_PROMPT = (
    "You are answering a question about a study area. Give your best estimate from what you know about this "
    'place and region; answer "insufficient_evidence" only where you cannot make an informed estimate. When '
    "finished, return your final answer as JSON following the provided schema."
)
TOOL_TIMEOUT = 1800  # seconds per tool call

SETTINGS = ("record", "closed_book", "no_image")


def _prompt(text: str) -> AgentPrompt:
    return AgentPrompt(instructions=text, handoff_prompt=None, assistant_prompt=None, submit_prompt=None)


def record_agent(fields: list[dict], image_tool: bool = True):
    """The agent with the record: bash, python, a text editor and, unless removed, the image viewer."""
    tools = [bash(timeout=TOOL_TIMEOUT), python(timeout=TOOL_TIMEOUT), text_editor()]
    if image_tool:
        tools.append(view_image())
    return react(name="earthrecord_agent", prompt=_prompt(SYSTEM_PROMPT), tools=tools,
                 submit=AgentSubmit(name="submit", tool=submit_tool(fields), answer_only=True))


def closed_book_agent(fields: list[dict]):
    """The closed book: the question and the site's bounding box, no data and no tools."""
    return react(name="earthrecord_closed_book", prompt=_prompt(CLOSED_BOOK_PROMPT), tools=[],
                 submit=AgentSubmit(name="submit", tool=submit_tool(fields, closed_book=True), answer_only=True))


@solver
def earthrecord_solver(setting: str = "record"):
    if setting not in SETTINGS:
        raise ValueError("setting must be one of %s" % ", ".join(SETTINGS))

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        fields = state.metadata["fields"]
        if setting == "closed_book":
            agent = closed_book_agent(fields)
        else:
            agent = record_agent(fields, image_tool=setting != "no_image")
        return await as_solver(agent)(state, generate)

    return solve
