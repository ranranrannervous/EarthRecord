"""Tools the agent has besides Inspect's bash, python and text editor: an image viewer and the answer submission."""

import base64
import json

from inspect_ai.model import ContentImage, ContentText
from inspect_ai.tool import ToolDef, ToolError, ToolParam, ToolParams, tool
from inspect_ai.util import sandbox

INSUFFICIENT_EVIDENCE = "insufficient_evidence"
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@tool
def view_image():
    async def execute(path: str):
        """Show an image file (PNG, JPEG, GIF or WebP) from the sandbox, for example a plot saved under /work.

        Args:
            path: Absolute path of the image file.
        """
        try:
            data = await sandbox().read_file(path, text=False)
        except FileNotFoundError:
            raise ToolError("File not found: " + path)
        if len(data) > MAX_IMAGE_BYTES:
            raise ToolError("Image larger than %d bytes" % MAX_IMAGE_BYTES)
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif data[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif data[:4] == b"GIF8":
            mime = "image/gif"
        elif data[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise ToolError("Not a PNG, JPEG, GIF or WebP file: " + path)
        encoded = base64.b64encode(data).decode()
        return [ContentText(text=path), ContentImage(image="data:%s;base64,%s" % (mime, encoded))]

    return execute


def _field_param(field: dict) -> ToolParam:
    """JSON schema of one answer field. Every field also accepts "insufficient_evidence"."""
    kind, options = field["kind"], field.get("options")
    description = field.get("desc") or field["name"].replace("_", " ")
    insufficient = ToolParam(type="string", enum=[INSUFFICIENT_EVIDENCE])
    if kind == "ci":
        return ToolParam(anyOf=[ToolParam(type="array", items=ToolParam(type="number")), ToolParam(type="null")],
                         description="95% confidence interval [lower, upper] of the estimate, or null")
    if kind == "set":
        return ToolParam(anyOf=[ToolParam(type="array", items=ToolParam(type="integer")), insufficient],
                         description=description)
    if kind == "choice" and options:
        return ToolParam(type="string", enum=list(options) + [INSUFFICIENT_EVIDENCE], description=description)
    if kind == "choice" and field.get("enum"):
        return ToolParam(type="string", enum=list(field["enum"]) + [INSUFFICIENT_EVIDENCE], description=description)
    if kind == "choice":
        return ToolParam(anyOf=[ToolParam(type="integer"), insufficient], description=description)
    if field.get("alt"):
        return ToolParam(anyOf=[ToolParam(type="number"),
                                ToolParam(type="string", enum=list(field["alt"]) + [INSUFFICIENT_EVIDENCE]),
                                ToolParam(type="null")], description=description)
    return ToolParam(anyOf=[ToolParam(type="number"), insufficient], description=description)


def submit_tool(fields: list[dict], closed_book: bool = False) -> ToolDef:
    """The submit tool of one question: its answer fields plus confidence, the data used, a method summary and caveats.

    In the closed book the agent has no data, so the field listing the data used is left out.
    """
    properties = {f["name"]: _field_param(f) for f in fields}
    properties.update({
        "confidence": ToolParam(type="integer", description="Confidence in the answer, 0-100"),
        "datasets_used": ToolParam(type="array", items=ToolParam(type="string"),
                                   description="Collections (directory names under /data) the answer is based on"),
        "method_summary": ToolParam(type="string", description="Short description of the method"),
        "caveats": ToolParam(type="string", description="Limitations and assumptions"),
    })
    if closed_book:
        del properties["datasets_used"]
    names = list(properties)

    async def execute(**kwargs) -> str:
        missing = [n for n in names if n not in kwargs]
        if missing:
            raise ToolError("missing fields: " + ", ".join(missing))
        confidence = kwargs.get("confidence")
        if not isinstance(confidence, int) or not 0 <= confidence <= 100:
            raise ToolError("confidence must be an integer between 0 and 100")
        return json.dumps({n: kwargs[n] for n in names})

    return ToolDef(execute, name="submit",
                   description="Submit the final answer. Call this once, when the analysis is finished.",
                   parameters=ToolParams(properties=properties, required=names))
