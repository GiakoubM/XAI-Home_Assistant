"""Model Relationships integration.

Stores a user-editable diagram of "model" boxes and the connections
between them, in a plain JSON file inside the Home Assistant config
directory (config/model_relationships_data.json) rather than in the
browser. That means:

  - Everyone who opens the dashboard on this HA instance sees the
    same diagram (no per-browser copies to get out of sync).
  - The diagram travels with your config: copy this integration
    folder, the card's .js file, and model_relationships_data.json
    to another Home Assistant instance and it shows up identically.

On every save, a static model_relationships.svg is also written to
the config folder - a plain image of the current diagram, viewable
in any browser or image tool, no Home Assistant required.

Exposed to the Lovelace frontend over the HA websocket API.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.sax.saxutils import escape

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

DOMAIN = "model_relationships"
DATA_FILENAME = "model_relationships_data.json"
SVG_FILENAME = "model_relationships.svg"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


class SvgDiagram:
    """Builds a static SVG snapshot of the diagram.

    Deliberately simple: render() always rebuilds the whole file from
    the current node/edge list rather than patching an existing SVG
    in place - surgical edits to hand-rolled XML get fragile fast.
    Add/remove/connect just change the lists passed in; render()
    always produces one clean, complete file.
    """

    BOX_W = 140
    BOX_H = 56
    PADDING = 30

    def __init__(self, nodes: list[dict], edges: list[dict]):
        self.nodes = nodes
        self.edges = edges

    def _node(self, node_id):
        return next((n for n in self.nodes if n.get("id") == node_id), None)

    @staticmethod
    def _edge_point(cx, cy, hw, hh, tx, ty):
        dx, dy = tx - cx, ty - cy
        if dx == 0 and dy == 0:
            return cx, cy
        sx = hw / abs(dx) if dx != 0 else float("inf")
        sy = hh / abs(dy) if dy != 0 else float("inf")
        s = min(sx, sy)
        return cx + dx * s, cy + dy * s

    def render(self) -> str:
        if not self.nodes:
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 120" '
                'width="400" height="120" font-family="sans-serif">'
                '<text x="200" y="60" text-anchor="middle" font-size="13" '
                'fill="#727272">No models yet</text></svg>'
            )

        max_x = max(n["x"] + self.BOX_W for n in self.nodes) + self.PADDING
        max_y = max(n["y"] + self.BOX_H for n in self.nodes) + self.PADDING

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {max_x:.0f} {max_y:.0f}" '
            f'width="{max_x:.0f}" height="{max_y:.0f}" font-family="sans-serif">',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#727272"></path></marker></defs>',
            f'<rect width="{max_x:.0f}" height="{max_y:.0f}" fill="#ffffff"></rect>',
        ]

        for edge in self.edges:
            a, b = self._node(edge.get("from")), self._node(edge.get("to"))
            if not a or not b:
                continue
            acx, acy = a["x"] + self.BOX_W / 2, a["y"] + self.BOX_H / 2
            bcx, bcy = b["x"] + self.BOX_W / 2, b["y"] + self.BOX_H / 2
            x1, y1 = self._edge_point(acx, acy, self.BOX_W / 2, self.BOX_H / 2, bcx, bcy)
            x2, y2 = self._edge_point(bcx, bcy, self.BOX_W / 2, self.BOX_H / 2, acx, acy)
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                'stroke="#bdbdbd" stroke-width="1.5" marker-end="url(#arrow)"></line>'
            )

        for n in self.nodes:
            x, y, label = n["x"], n["y"], n.get("label", "")
            parts.append(
                f'<g transform="translate({x:.1f},{y:.1f})">'
                f'<rect width="{self.BOX_W}" height="{self.BOX_H}" rx="8" '
                'fill="#ffffff" stroke="#bdbdbd" stroke-width="1"></rect>'
                f'<text x="{self.BOX_W / 2}" y="{self.BOX_H / 2 + 1}" text-anchor="middle" '
                'dominant-baseline="middle" font-size="13" font-weight="500" '
                f'fill="#212121">{escape(label)}</text></g>'
            )

        parts.append('</svg>')
        return ''.join(parts)


def _read_file(path: Path) -> dict:
    if not path.exists():
        return {"nodes": [], "edges": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        _LOGGER.warning("Could not read %s: %s", path, err)
        return {"nodes": [], "edges": []}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data[DOMAIN] = {
        "path": Path(hass.config.path(DATA_FILENAME)),
        "svg_path": Path(hass.config.path(SVG_FILENAME)),
    }

    websocket_api.async_register_command(hass, ws_get_data)
    websocket_api.async_register_command(hass, ws_save_data)
    websocket_api.async_register_command(hass, ws_create_view)

    return True


@websocket_api.websocket_command({vol.Required("type"): "model_relationships/get"})
@websocket_api.async_response
async def ws_get_data(hass: HomeAssistant, connection, msg):
    path = hass.data[DOMAIN]["path"]
    data = await hass.async_add_executor_job(_read_file, path)
    connection.send_result(msg["id"], data)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "model_relationships/save",
        vol.Required("nodes"): list,
        vol.Required("edges"): list,
    }
)
@websocket_api.async_response
async def ws_save_data(hass: HomeAssistant, connection, msg):
    data_path = hass.data[DOMAIN]["path"]
    svg_path = hass.data[DOMAIN]["svg_path"]
    data = {"nodes": msg["nodes"], "edges": msg["edges"]}
    svg = SvgDiagram(data["nodes"], data["edges"]).render()
    await hass.async_add_executor_job(_write_json, data_path, data)
    await hass.async_add_executor_job(_write_text, svg_path, svg)
    connection.send_result(msg["id"], {"saved": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "model_relationships/create_view",
        vol.Required("dashboard"): str,
        vol.Required("model_id"): str,
        vol.Required("title"): str,
        vol.Optional("inputs", default=[]): [str],
        vol.Optional("outputs", default=[]): [str],
    }
)
@websocket_api.async_response
async def ws_create_view(hass: HomeAssistant, connection, msg):
    """Create or update a dashboard view listing a model's inputs/outputs.

    NOTE: this touches Home Assistant's internal Lovelace dashboard
    storage (hass.data["lovelace"]), which is not a documented,
    stable integration API - unlike the get/save commands above, this
    one is more likely to need adjusting after a future HA core
    upgrade. It only works against "storage" mode dashboards (the
    default for dashboards created from the UI); YAML-mode dashboards
    can't be edited this way.
    """
    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        connection.send_error(msg["id"], "lovelace_unavailable", "Lovelace is not ready yet")
        return

    dashboards = getattr(lovelace_data, "dashboards", None)
    if dashboards is None and isinstance(lovelace_data, dict):
        dashboards = lovelace_data.get("dashboards")
    if dashboards is None:
        connection.send_error(
            msg["id"],
            "unsupported_ha_version",
            "Could not locate dashboard storage for this Home Assistant version",
        )
        return

    dashboard_key = msg["dashboard"] or None
    storage = dashboards.get(dashboard_key)
    if storage is None and dashboard_key is not None:
        # fall back to the default dashboard if the named one isn't a
        # separately stored dashboard
        storage = dashboards.get(None)
    if storage is None:
        connection.send_error(
            msg["id"],
            "dashboard_not_found",
            f"Could not find a storage-mode dashboard '{msg['dashboard']}'",
        )
        return

    try:
        config = await storage.async_load(False)
        views = config.setdefault("views", [])

        cards = []
        if msg["inputs"]:
            cards.append({"type": "markdown", "content": "## Inputs"})
            cards.append({
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [{"type": "tile", "entity": entity_id} for entity_id in msg["inputs"]],
            })
        if msg["outputs"]:
            cards.append({"type": "markdown", "content": "## Outputs"})
            cards.append({
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": [{"type": "tile", "entity": entity_id} for entity_id in msg["outputs"]],
            })
        if not cards:
            cards.append({"type": "markdown", "content": "No inputs or outputs added yet."})

        view_path = f"model-{msg['model_id']}"
        new_view = {"title": msg["title"], "path": view_path, "subview": True, "cards": cards}

        existing_view = next((v for v in views if v.get("path") == view_path), None)
        if existing_view is not None:
            existing_view.update(new_view)
        else:
            views.append(new_view)

        await storage.async_save(config)
    except Exception as err:  # noqa: BLE001 - surface any internal-API mismatch to the UI
        _LOGGER.exception("Could not create/update subview for model %s", msg["model_id"])
        connection.send_error(msg["id"], "create_view_failed", str(err))
        return

    connection.send_result(msg["id"], {"path": view_path})
