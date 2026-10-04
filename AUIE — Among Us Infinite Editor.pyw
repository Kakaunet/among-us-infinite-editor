from __future__ import annotations

import base64
import json
import math
import os
import shutil
import struct
import webbrowser
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, List, Tuple

APP_TITLE = "Among Us Infinite Editor"
SUPPORTED_MIN_VERSION = 7


# ---------------------------------------------------------------------------
# Credits tab customization
# ---------------------------------------------------------------------------
# Edit this text to customize the Credits tab. The displayed text is read-only
# while the program is running. Use CREDIT_LINKS below for clickable website buttons.
CREDIT_TEXT = """Among Us Infinite Editor — AUIE 1.0.0

Made for Among Us v19s (v19.0.0).

Created by Kakaunet (on GitHub).

rAIting: Z.r-u

Special thanks to ChatGPT by OpenAI (well, they did all the work).

This is an independent fan-made utility and is not affiliated with, endorsed by,
or sponsored by Innersloth LLC. Among Us and related names are trademarks of
their respective owners.
"""

# Format: (button label, URL). Add, remove, or edit entries as needed.
CREDIT_LINKS = [
    ("AUIE GitHub", "https://github.com/Kakaunet/among-us-infinite-editor"),
    ("AUIE rAIting", "https://github.com/Kakaunet/among-us-infinite-editor/blob/main/rAIting_Z.r-u.md"),
    ("Among Us — by Innersloth", "https://www.innersloth.com/games/among-us/"),
]

DEFAULT_SETTINGS_PATH = (
    Path(os.environ.get("USERPROFILE", Path.home()))
    / "AppData" / "LocalLow" / "Innersloth" / "Among Us" / "settings.amogus"
)

# Built-in v19-format Normal options fallback. This is also used for the
# first-run "Chaos" preset.
DEFAULT_BLOB = (
    "DJQAAAEAZA8AAQAAAAAA4D8AAABAAAAAQG8SgzoBAQEDAAAAAQAeAAAAHgAAAAAKAQEBAAALBQABZAMAAAEA/wIAAmQCAAAA/wQAAWQDAAAA/wEDAANkAgAAAP8JAAFkAgAAAP8KAAJkAwAAAP8ACAADZAIAAP8BDAACZAEAAAQSAAFkAQAAChMAAmQBAAAAFQALZAEAAAA="
)
DEFAULT_PRESET_NAME = "Chaos"

MAP_NAMES = {
    0: "The Skeld",
    1: "MIRA HQ",
    2: "Polus",
    4: "The Airship",
    5: "The Fungle",
}

KILL_DISTANCE_NAMES = {0: "Short", 1: "Medium", 2: "Long"}
TASKBAR_NAMES = {0: "Always", 1: "Meetings", 2: "Never"}
GAME_MODE_NAMES = {1: "Normal", 3: "Normal Fools"}

PRESETS_PATH = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "Among Us Infinite Editor"
    / "presets.json"
)

GENERAL_ENUMS = {
    "map_id": MAP_NAMES,
    "kill_distance": KILL_DISTANCE_NAMES,
    "taskbar_updates": TASKBAR_NAMES,
    "game_mode": GAME_MODE_NAMES,
}

IMPOSTOR_ROLE_IDS = {5, 9, 18}
GHOST_CREWMATE_ROLE_IDS = {4, 21}

ROLE_NAMES = {
    2: "Scientist",
    3: "Engineer",
    4: "Guardian Angel",
    5: "Shapeshifter",
    8: "Noisemaker",
    9: "Phantom",
    10: "Tracker",
    12: "Detective",
    18: "Viper",
    19: "Judge",
    21: "Influencer",
}

# Current role payload layout for Normal options (v19 style).
# type: u8 / bool. Values outside normal UI ranges remain editable unless they
# violate the serialized type.
ROLE_SCHEMAS = {
    2: [("Vitals Display Cooldown", "u8"), ("Battery Duration", "u8")],
    3: [("Vent Use Cooldown", "u8"), ("Max Time In Vents", "u8")],
    4: [("Protect Cooldown", "u8"), ("Protect Duration", "u8"), ("Protect Visible To Impostors", "bool")],
    5: [("Leave Shape-Shifting Evidence", "bool"), ("Shapeshift Cooldown", "u8"), ("Shapeshift Duration", "u8")],
    8: [("Alert Duration", "u8"), ("Impostor Gets Alert", "bool")],
    9: [("Vanish Cooldown", "u8"), ("Vanish Duration", "u8")],
    10: [("Tracking Cooldown", "u8"), ("Tracking Duration", "u8"), ("Tracking Delay", "u8")],
    12: [("Suspects per Case", "u8")],
    18: [("Dissolve Duration", "u8")],
    19: [("Tasks Required for Overrule", "u8")],
    21: [("Message Cooldown", "u8")],
}

ROLE_OPTION_NOTES = {
    (2, 0): "Cooldown for the Scientist's portable Vitals display.",
    (2, 1): "How long the Scientist can keep portable Vitals active per charge.",
    (3, 0): "Cooldown before the Engineer can use vents again.",
    (3, 1): "Maximum continuous time the Engineer can remain in a vent.",
    (4, 0): "Cooldown between Guardian Angel Protect uses.",
    (4, 1): "How long a Guardian Angel protection remains active.",
    (4, 2): "Whether Impostors can see active Guardian Angel protection.",
    (5, 0): "Whether Shapeshifting leaves visible evidence behind.",
    (5, 1): "Cooldown between Shapeshift uses.",
    (5, 2): "How long a Shapeshift lasts; some builds treat 0 as indefinite.",
    (8, 0): "How long the Noisemaker death alert remains visible.",
    (8, 1): "Whether Impostors also receive the Noisemaker death alert.",
    (9, 0): "Cooldown between Phantom Vanish uses.",
    (9, 1): "Maximum duration of a Phantom Vanish.",
    (10, 0): "Cooldown between Tracker tracking uses.",
    (10, 1): "How long a tracked player's position remains tracked.",
    (10, 2): "Delay before the Tracker begins receiving position updates.",
    (12, 0): "Maximum number of suspects available to the Detective per case.",
    (18, 0): "Time used by the Viper's body-dissolve effect.",
    (19, 0): "Number of tasks the Judge must complete before Overrule becomes available.",
    (21, 0): "Cooldown between Influencer Message ability uses.",
}


class ParseError(ValueError):
    pass


def clamp_int(value: int, lo: int, hi: int) -> Tuple[int, bool]:
    nv = max(lo, min(hi, value))
    return nv, nv != value


def finite_float(value: float, fallback: float = 0.0) -> Tuple[float, bool]:
    if not math.isfinite(value):
        return fallback, True
    return value, False


def read_u8(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 1 > len(data):
        raise ParseError("Unexpected end of data while reading uint8")
    return data[pos], pos + 1


def read_u16(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 2 > len(data):
        raise ParseError("Unexpected end of data while reading uint16")
    return struct.unpack_from("<H", data, pos)[0], pos + 2


def read_u32(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 4 > len(data):
        raise ParseError("Unexpected end of data while reading uint32")
    return struct.unpack_from("<I", data, pos)[0], pos + 4


def read_i32(data: bytes, pos: int) -> Tuple[int, int]:
    if pos + 4 > len(data):
        raise ParseError("Unexpected end of data while reading int32")
    return struct.unpack_from("<i", data, pos)[0], pos + 4


def read_f32(data: bytes, pos: int) -> Tuple[float, int]:
    if pos + 4 > len(data):
        raise ParseError("Unexpected end of data while reading float32")
    return struct.unpack_from("<f", data, pos)[0], pos + 4


def read_packed_uint(data: bytes, pos: int) -> Tuple[int, int]:
    value = 0
    shift = 0
    while True:
        b, pos = read_u8(data, pos)
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, pos
        shift += 7
        if shift > 35:
            raise ParseError("Packed integer is too large")


def write_packed_uint(value: int) -> bytes:
    if value < 0:
        raise ValueError("packed uint cannot be negative")
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def read_hazel_message(data: bytes, pos: int) -> Tuple[int, bytes, int]:
    length, pos = read_u16(data, pos)
    tag, pos = read_u8(data, pos)
    end = pos + length
    if end > len(data):
        raise ParseError("Hazel message length exceeds available data")
    return tag, data[pos:end], end


def write_hazel_message(payload: bytes, tag: int = 0) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError("Hazel message payload is too large")
    return struct.pack("<H", len(payload)) + bytes([tag & 0xFF]) + payload


@dataclass
class RoleRecord:
    role_id: int
    max_players: int
    chance: int
    message_tag: int = 0
    payload: bytearray = field(default_factory=bytearray)

    @property
    def name(self) -> str:
        return ROLE_NAMES.get(self.role_id, f"Unknown Role {self.role_id}")

    def decoded_options(self) -> Dict[str, object]:
        schema = ROLE_SCHEMAS.get(self.role_id)
        if not schema:
            return {}
        out = {}
        for i, (name, typ) in enumerate(schema):
            if i >= len(self.payload):
                break
            raw = self.payload[i]
            out[name] = bool(raw) if typ == "bool" else raw
        return out

    def set_option(self, index: int, typ: str, value: object):
        while len(self.payload) <= index:
            self.payload.append(0)
        if typ == "bool":
            self.payload[index] = 1 if bool(value) else 0
        else:
            iv = int(value)
            iv, _ = clamp_int(iv, 0, 255)
            self.payload[index] = iv


@dataclass
class NormalHostOptions:
    version: int = 12
    outer_tag: int = 0
    game_mode: int = 1
    special_mode: int = 0
    rules_preset: int = 100
    max_players: int = 15
    keywords: int = 256
    map_id: int = 0
    player_speed: float = 1.0
    crewmate_vision: float = 1.0
    impostor_vision: float = 1.5
    kill_cooldown: float = 15.0
    common_tasks: int = 1
    long_tasks: int = 1
    short_tasks: int = 2
    emergency_meetings: int = 1
    impostors: int = 1
    kill_distance: int = 1
    discussion_time: int = 15
    voting_time: int = 120
    is_defaults: bool = False
    emergency_cooldown: int = 15
    confirm_ejects: bool = True
    visual_tasks: bool = True
    anonymous_votes: bool = False
    taskbar_updates: int = 0
    tag: int = 0
    roles: List[RoleRecord] = field(default_factory=list)
    payload_trailing_bytes: bytes = b""
    outer_trailing_bytes: bytes = b""

    @classmethod
    def decode(cls, blob: str) -> "NormalHostOptions":
        try:
            raw = base64.b64decode("".join(blob.split()), validate=True)
        except Exception as e:
            raise ParseError(f"Invalid Base64: {e}") from e
        if len(raw) < 4:
            raise ParseError("Blob is too short")

        pos = 0
        version, pos = read_u8(raw, pos)
        if version < SUPPORTED_MIN_VERSION:
            raise ParseError(f"This editor supports version {SUPPORTED_MIN_VERSION}+ blobs; got version {version}")

        outer_tag, payload, pos = read_hazel_message(raw, pos)
        if pos != len(raw):
            # Preserve bytes beyond the outer message instead of discarding them.
            outer_trailing = raw[pos:]
        else:
            outer_trailing = b""

        p = 0
        obj = cls(version=version, outer_tag=outer_tag)
        obj.game_mode, p = read_u8(payload, p)
        if obj.game_mode == 0:
            raise ParseError("GameMode.None has no editable Normal host settings")
        obj.special_mode, p = read_u8(payload, p)
        obj.rules_preset, p = read_u8(payload, p)
        obj.max_players, p = read_u8(payload, p)
        obj.keywords, p = read_u32(payload, p)
        obj.map_id, p = read_u8(payload, p)
        obj.player_speed, p = read_f32(payload, p)
        obj.crewmate_vision, p = read_f32(payload, p)
        obj.impostor_vision, p = read_f32(payload, p)

        # settings.amogus Normal host options use the Normal / NormalFools schema here.
        # For other game modes we stop rather than corrupt a different schema.
        if obj.game_mode not in (1, 3):
            raise ParseError(
                f"Game mode {obj.game_mode} is not a Normal-mode blob. "
                "This editor intentionally refuses to reinterpret Hide n Seek bytes as Normal settings."
            )

        obj.kill_cooldown, p = read_f32(payload, p)
        obj.common_tasks, p = read_u8(payload, p)
        obj.long_tasks, p = read_u8(payload, p)
        obj.short_tasks, p = read_u8(payload, p)
        obj.emergency_meetings, p = read_i32(payload, p)
        obj.impostors, p = read_u8(payload, p)
        obj.kill_distance, p = read_u8(payload, p)
        obj.discussion_time, p = read_i32(payload, p)
        obj.voting_time, p = read_i32(payload, p)
        v, p = read_u8(payload, p); obj.is_defaults = bool(v)
        obj.emergency_cooldown, p = read_u8(payload, p)
        v, p = read_u8(payload, p); obj.confirm_ejects = bool(v)
        v, p = read_u8(payload, p); obj.visual_tasks = bool(v)
        v, p = read_u8(payload, p); obj.anonymous_votes = bool(v)
        obj.taskbar_updates, p = read_u8(payload, p)
        obj.tag, p = read_u8(payload, p)

        role_count, p = read_packed_uint(payload, p)
        roles = []
        for _ in range(role_count):
            role_id, p = read_u16(payload, p)
            max_players, p = read_u8(payload, p)
            chance, p = read_u8(payload, p)
            msg_tag, role_payload, p = read_hazel_message(payload, p)
            roles.append(RoleRecord(role_id, max_players, chance, msg_tag, bytearray(role_payload)))
        obj.roles = roles
        obj.payload_trailing_bytes = payload[p:]
        obj.outer_trailing_bytes = outer_trailing
        return obj

    def sanitize(self, compatibility_guard: bool = True, prevent_invalid_values: bool = True) -> List[str]:
        """Validate or repair values against serialization limits.

        Normal in-game menu limits are intentionally not enforced. When
        prevent_invalid_values is enabled, values that cannot be represented by
        the binary format are repaired; otherwise they raise ValueError.
        """
        changes = []

        def checked_int(attr: str, lo: int, hi: int, label: str | None = None):
            old = int(getattr(self, attr))
            if lo <= old <= hi:
                return
            if not prevent_invalid_values:
                raise ValueError(f"{label or attr} must be between {lo} and {hi}; got {old}")
            new = max(lo, min(hi, old))
            setattr(self, attr, new)
            changes.append(f"{label or attr}: {old} -> {new} (code limit {lo}..{hi})")

        # Byte-backed header/gameplay fields must fit the serializer. Max Players
        # has an additional hard game constraint: Among Us lobbies are valid only
        # from 4 through 15 players. We deliberately do NOT enforce ordinary
        # menu limits for experimental settings such as role counts/chances.
        for attr in (
            "game_mode", "special_mode", "rules_preset", "map_id",
            "common_tasks", "long_tasks", "short_tasks", "impostors", "kill_distance",
            "emergency_cooldown", "taskbar_updates", "tag"
        ):
            checked_int(attr, 0, 255)

        checked_int("max_players", 4, 15, "Max Players")
        checked_int("keywords", 0, 0xFFFFFFFF)
        for attr in ("emergency_meetings", "discussion_time", "voting_time"):
            checked_int(attr, -0x80000000, 0x7FFFFFFF)

        FLOAT32_MAX = 3.4028234663852886e38
        for attr in ("player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"):
            old = float(getattr(self, attr))
            if math.isfinite(old) and -FLOAT32_MAX <= old <= FLOAT32_MAX:
                continue
            if not prevent_invalid_values:
                raise ValueError(f"{attr} must be a finite float32 value")
            if not math.isfinite(old):
                new = 0.0
                changes.append(f"{attr}: non-finite -> 0.0")
            else:
                new = max(-FLOAT32_MAX, min(FLOAT32_MAX, old))
                changes.append(f"{attr}: {old} -> {new} (float32 code limit)")
            setattr(self, attr, new)

        for role in self.roles:
            # Both fields are serialized as unsigned bytes. Values above the
            # normal in-game UI ranges are intentionally allowed for testing;
            # only values that cannot fit in the binary field are repaired.
            if not 0 <= int(role.max_players) <= 255:
                if not prevent_invalid_values:
                    raise ValueError(f"{role.name} max players must fit in one byte (0..255); got {role.max_players}")
                old = role.max_players
                role.max_players = max(0, min(255, int(role.max_players)))
                changes.append(f"{role.name} max players: {old} -> {role.max_players} (byte limit)")
            if not 0 <= int(role.chance) <= 255:
                if not prevent_invalid_values:
                    raise ValueError(f"{role.name} chance must fit in one byte (0..255); got {role.chance}")
                old = role.chance
                role.chance = max(0, min(255, int(role.chance)))
                changes.append(f"{role.name} chance: {old} -> {role.chance} (byte limit)")

        if compatibility_guard and self.kill_cooldown <= 0:
            old = self.kill_cooldown
            self.kill_cooldown = 0.001
            changes.append(f"kill_cooldown: {old} -> 0.001 (compatibility guard for exact-zero kill cooldown)")

        return changes

    def encode(self, compatibility_guard: bool = True, prevent_invalid_values: bool = True) -> Tuple[str, List[str]]:
        changes = self.sanitize(compatibility_guard, prevent_invalid_values)

        payload = bytearray()
        payload += struct.pack("<B", self.game_mode)
        payload += struct.pack("<B", self.special_mode)
        payload += struct.pack("<B", self.rules_preset)
        payload += struct.pack("<B", self.max_players)
        payload += struct.pack("<I", self.keywords)
        payload += struct.pack("<B", self.map_id)
        payload += struct.pack("<f", self.player_speed)
        payload += struct.pack("<f", self.crewmate_vision)
        payload += struct.pack("<f", self.impostor_vision)
        payload += struct.pack("<f", self.kill_cooldown)
        payload += struct.pack("<B", self.common_tasks)
        payload += struct.pack("<B", self.long_tasks)
        payload += struct.pack("<B", self.short_tasks)
        payload += struct.pack("<i", self.emergency_meetings)
        payload += struct.pack("<B", self.impostors)
        payload += struct.pack("<B", self.kill_distance)
        payload += struct.pack("<i", self.discussion_time)
        payload += struct.pack("<i", self.voting_time)
        payload += struct.pack("<B", int(bool(self.is_defaults)))
        payload += struct.pack("<B", self.emergency_cooldown)
        payload += struct.pack("<B", int(bool(self.confirm_ejects)))
        payload += struct.pack("<B", int(bool(self.visual_tasks)))
        payload += struct.pack("<B", int(bool(self.anonymous_votes)))
        payload += struct.pack("<B", self.taskbar_updates)
        payload += struct.pack("<B", self.tag)
        payload += write_packed_uint(len(self.roles))

        for role in self.roles:
            payload += struct.pack("<HBB", role.role_id, role.max_players, role.chance)
            payload += write_hazel_message(bytes(role.payload), role.message_tag)

        # Preserve unknown bytes in the same structural location where they were decoded.
        payload += self.payload_trailing_bytes
        raw = (
            bytes([self.version & 0xFF])
            + write_hazel_message(bytes(payload), self.outer_tag)
            + self.outer_trailing_bytes
        )
        return base64.b64encode(raw).decode("ascii"), changes


class ScrollFrame(ttk.Frame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas = canvas


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x820")
        self.minsize(920, 680)
        self.options: NormalHostOptions | None = None
        self.general_vars: Dict[str, tk.Variable] = {}
        self.role_vars: Dict[Tuple[int, str], tk.Variable] = {}
        self.compat_guard = tk.BooleanVar(value=True)
        self.prevent_invalid_values = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready")
        self.preset_var = tk.StringVar()
        self.loaded_settings_path: Path | None = None
        self.role_capacity_vars = {
            "crew": tk.StringVar(value="Maximum Population: —\nWith Roles: —\nExcess Roles: —\nWithout Roles: —"),
            "impostor": tk.StringVar(value="Population: —\nWith Roles: —\nExcess Roles: —\nWithout Roles: —"),
            "ghost1": tk.StringVar(value="Maximum Population: —\nWith Roles: —\nExcess Roles: —\nWithout Roles: —"),
            "ghost2": tk.StringVar(value="Maximum Population: —\nWith Roles: —\nExcess Roles: —\nWithout Roles: —"),
            "ghost3": tk.StringVar(value="Maximum Population: —\nWith Roles: —\nExcess Roles: —\nWithout Roles: —"),
        }
        self._build_ui()
        self._initialize_first_run_presets()
        # If there is no explicit startup source to restore, use the built-in
        # Chaos configuration as the editor's safe, known fallback.
        self.load_blob(DEFAULT_BLOB, quiet=True)
        self._refresh_presets()
        if DEFAULT_PRESET_NAME in self._read_presets():
            self.preset_var.set(DEFAULT_PRESET_NAME)

    @staticmethod
    def _enum_label(mapping: Dict[int, str], value: int) -> str:
        name = mapping.get(value, "Unknown")
        return f"{name} ({value})"

    @staticmethod
    def _enum_value(mapping: Dict[int, str], label: str) -> int:
        for value, name in mapping.items():
            if label == f"{name} ({value})":
                return value
        # Defensive fallback if a value was programmatically inserted.
        if label.rstrip().endswith(")") and "(" in label:
            try:
                return int(label.rsplit("(", 1)[1][:-1])
            except ValueError:
                pass
        raise ValueError(f"Unsupported selection: {label}")

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 16, "bold")).pack(side="left")

        safety_box = ttk.Frame(top)
        safety_box.pack(side="right", anchor="ne")
        ttk.Checkbutton(
            safety_box,
            text="Protect kill cooldown from exact 0",
            variable=self.compat_guard,
            command=lambda: self._commit_general_field("kill_cooldown") if self.compat_guard.get() else None,
        ).pack(anchor="w")
        ttk.Checkbutton(
            safety_box,
            text="Prevent invalid / crash-prone values",
            variable=self.prevent_invalid_values,
            command=lambda: self._validate_all_visible_fields() if self.prevent_invalid_values.get() else None,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            safety_box,
            text="Hard/code limits only — not ordinary menu limits",
            foreground="#666",
        ).pack(anchor="w", padx=(22, 0), pady=(0, 1))

        # File actions stay visible regardless of the selected tab.
        filebar = ttk.Frame(self, padding=(10, 0, 10, 8))
        filebar.pack(fill="x")
        ttk.Button(
            filebar, text="Load from settings.amogus", command=self.load_default_settings
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            filebar, text="Save to settings.amogus", command=self.save_to_settings
        ).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.general_tab = ScrollFrame(self.notebook)
        self.roles_tab = ScrollFrame(self.notebook)
        self.io_tab = ttk.Frame(self.notebook, padding=10)
        self.presets_tab = ttk.Frame(self.notebook, padding=10)
        self.advanced_tab = ttk.Frame(self.notebook, padding=10)
        self.credits_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.general_tab, text="General")
        self.notebook.add(self.roles_tab, text="Roles")
        self.notebook.add(self.io_tab, text="Import / Export")
        self.notebook.add(self.presets_tab, text="Presets")
        self.notebook.add(self.advanced_tab, text="Advanced")
        self.notebook.add(self.credits_tab, text="Credits")

        self._build_general()
        self._build_io()
        self._build_presets()
        self._build_advanced()
        self._build_credits()

        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(
            fill="x", side="bottom"
        )

    def _bind_commit_events(self, widget, callback):
        """Run a numeric-field commit after Enter/numpad Enter or when focus leaves the field.

        ``after_idle`` ensures Tk has already copied the final edited text into the
        associated variable before validation runs.
        """
        def schedule(_event=None):
            self.after_idle(callback)

        widget.bind("<Return>", schedule, add="+")
        widget.bind("<KP_Enter>", schedule, add="+")
        widget.bind("<FocusOut>", schedule, add="+")

    def _add_entry(self, parent, row, label, key, vartype="str", width=18, note=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        if vartype == "bool":
            var = tk.BooleanVar()
            widget = ttk.Checkbutton(parent, variable=var)
        else:
            cls = tk.DoubleVar if vartype == "float" else tk.IntVar if vartype == "int" else tk.StringVar
            var = cls()
            widget = ttk.Entry(parent, textvariable=var, width=width)
        widget.grid(row=row, column=1, sticky="w", padx=6, pady=4)
        if note:
            ttk.Label(parent, text=note, foreground="#666").grid(row=row, column=2, sticky="w", padx=6)
        self.general_vars[key] = var
        if vartype in {"int", "float"}:
            self._bind_commit_events(widget, lambda field=key: self._commit_general_field(field))

    def _add_enum(self, parent, row, label, key, mapping: Dict[int, str], width=26, note=""):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        var = tk.StringVar()
        values = [self._enum_label(mapping, value) for value in mapping]
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width)
        combo.grid(row=row, column=1, sticky="w", padx=6, pady=4)
        if note:
            ttk.Label(parent, text=note, foreground="#666").grid(row=row, column=2, sticky="w", padx=6)
        self.general_vars[key] = var

    def _build_general(self):
        p = self.general_tab.inner
        p.columnconfigure(2, weight=1)
        r = 0
        ttk.Label(p, text="Normal game settings", font=("Segoe UI", 12, "bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 5)
        ); r += 1
        ttk.Label(
            p,
            text=("Only settings with a clear in-game meaning are editable here. Internal/version-specific "
                  "header metadata is preserved automatically when a blob is decoded and regenerated."),
            foreground="#555", wraplength=900,
        ).grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 8)); r += 1

        self._add_entry(
            p, r, "Max Players", "max_players", "int",
            note="Lobby size. This is treated as a hard safety limit: Among Us lobbies require 4–15 players."
        ); r += 1
        self._add_enum(
            p, r, "Map", "map_id", MAP_NAMES,
            note="Map used for the match; the serialized ID is shown in parentheses."
        ); r += 1
        self._add_entry(
            p, r, "Player Speed", "player_speed", "float",
            note="Movement-speed multiplier for all players (1.0 = normal speed)."
        ); r += 1
        self._add_entry(
            p, r, "Crewmate Vision", "crewmate_vision", "float",
            note="Crewmate vision-radius multiplier (1.0 = normal)."
        ); r += 1
        self._add_entry(
            p, r, "Impostor Vision", "impostor_vision", "float",
            note="Impostor vision-radius multiplier (1.0 = normal)."
        ); r += 1
        self._add_entry(
            p, r, "Kill Cooldown", "kill_cooldown", "float",
            note="Seconds between Impostor kills. Exact 0 may disable killing in some builds; the optional guard substitutes 0.001."
        ); r += 1
        self._add_entry(
            p, r, "Common Tasks", "common_tasks", "int",
            note="Number of common tasks assigned to every Crewmate."
        ); r += 1
        self._add_entry(
            p, r, "Long Tasks", "long_tasks", "int",
            note="Number of long tasks assigned to each Crewmate."
        ); r += 1
        self._add_entry(
            p, r, "Short Tasks", "short_tasks", "int",
            note="Number of short tasks assigned to each Crewmate."
        ); r += 1
        self._add_entry(
            p, r, "Emergency Meetings", "emergency_meetings", "int",
            note="How many emergency meetings each player may call."
        ); r += 1
        self._add_entry(
            p, r, "Impostors", "impostors", "int",
            note="Number of Impostors selected for the match. Standard lobbies support 1–3, subject to lobby size."
        ); r += 1
        self._add_enum(
            p, r, "Kill Distance", "kill_distance", KILL_DISTANCE_NAMES,
            note="Maximum range at which an Impostor can perform a kill."
        ); r += 1
        self._add_entry(
            p, r, "Discussion Time", "discussion_time", "int",
            note="Seconds at the start of a meeting before voting becomes available."
        ); r += 1
        self._add_entry(
            p, r, "Voting Time", "voting_time", "int",
            note="Seconds available for voting once the voting phase begins."
        ); r += 1
        self._add_entry(
            p, r, "Emergency Cooldown", "emergency_cooldown", "int",
            note="Seconds players must wait between emergency-button meetings."
        ); r += 1
        self._add_entry(
            p, r, "Confirm Ejects", "confirm_ejects", "bool",
            note="If enabled, ejection text reveals whether the ejected player was an Impostor."
        ); r += 1
        self._add_entry(
            p, r, "Visual Tasks", "visual_tasks", "bool",
            note="If enabled, other players can see visual task animations such as MedBay scan / asteroids."
        ); r += 1
        self._add_entry(
            p, r, "Anonymous Votes", "anonymous_votes", "bool",
            note="If enabled, meeting vote icons do not reveal each voter's player color."
        ); r += 1
        self._add_enum(
            p, r, "Task Bar Updates", "taskbar_updates", TASKBAR_NAMES,
            note="Controls when the global task-progress bar visibly updates."
        ); r += 1

        ttk.Separator(p).grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=10); r += 1
        ttk.Label(p, text="Preserved compatibility metadata", font=("Segoe UI", 10, "bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=6
        ); r += 1
        ttk.Label(
            p,
            text=("The editor still preserves the blob version, game-mode discriminator, lobby keyword bitfield, "
                  "default-state flag, Hazel tags, and newer undocumented header bytes. They are intentionally "
                  "not editable here because they are either serialization metadata, lobby/discovery metadata, "
                  "or version-dependent fields whose meaning is not documented well enough to expose safely."),
            foreground="#666", wraplength=920, justify="left",
        ).grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=(3, 10))

        # These two values define the available living-team populations shown on
        # the Roles tab. The summary is read-only but updates immediately while
        # the user edits either field.
        self.general_vars["max_players"].trace_add("write", lambda *_: self._update_role_capacity_summary())
        self.general_vars["impostors"].trace_add("write", lambda *_: self._update_role_capacity_summary())

    def _role_card(self, parent, idx: int, role: RoleRecord):
        box = ttk.LabelFrame(parent, text=f"{role.name}  [role id {role.role_id}]", padding=8)
        box.pack(fill="x", padx=6, pady=6)
        box.columnconfigure(3, weight=1)

        max_var = tk.IntVar(value=role.max_players)
        chance_var = tk.IntVar(value=role.chance)
        self.role_vars[(idx, "max_players")] = max_var
        self.role_vars[(idx, "chance")] = chance_var
        max_var.trace_add("write", lambda *_: self._update_role_capacity_summary())
        chance_var.trace_add("write", lambda *_: self._update_role_capacity_summary())
        ttk.Label(box, text="Max players").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        max_entry = ttk.Entry(box, textvariable=max_var, width=10)
        max_entry.grid(row=0, column=1, sticky="w", padx=4)
        self._bind_commit_events(max_entry, lambda i=idx: self._commit_role_field(i, "max_players"))
        ttk.Label(box, text="Chance value").grid(row=0, column=2, sticky="w", padx=(18, 4))
        chance_entry = ttk.Entry(box, textvariable=chance_var, width=10)
        chance_entry.grid(row=0, column=3, sticky="w", padx=4)
        self._bind_commit_events(chance_entry, lambda i=idx: self._commit_role_field(i, "chance"))

        schema = ROLE_SCHEMAS.get(role.role_id)
        if schema:
            for j, (name, typ) in enumerate(schema):
                row = j + 1
                ttk.Label(box, text=name).grid(row=row, column=0, sticky="w", padx=4, pady=3)
                current = role.payload[j] if j < len(role.payload) else 0
                note = ROLE_OPTION_NOTES.get((role.role_id, j), "")
                if typ == "bool":
                    var = tk.BooleanVar(value=bool(current))
                    ttk.Checkbutton(box, variable=var).grid(row=row, column=1, sticky="w", padx=4)
                    detail = note or "Boolean option."
                else:
                    var = tk.IntVar(value=current)
                    option_entry = ttk.Entry(box, textvariable=var, width=10)
                    option_entry.grid(row=row, column=1, sticky="w", padx=4)
                    self._bind_commit_events(option_entry, lambda i=idx, n=j: self._commit_role_field(i, f"payload_{n}"))
                    detail = (note + "  " if note else "") + "Stored as an unsigned byte (0–255)."
                ttk.Label(box, text=detail, foreground="#666", wraplength=620, justify="left").grid(
                    row=row, column=2, columnspan=2, sticky="w", padx=4
                )
                self.role_vars[(idx, f"payload_{j}")] = var
        else:
            raw_var = tk.StringVar(value=role.payload.hex(" "))
            self.role_vars[(idx, "raw_payload")] = raw_var
            ttk.Label(box, text="Unknown payload (hex)").grid(row=1, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(box, textvariable=raw_var, width=70).grid(row=1, column=1, columnspan=3, sticky="ew", padx=4)

    @staticmethod
    def _safe_var_int(var, fallback=0):
        try:
            return int(var.get())
        except (tk.TclError, ValueError, TypeError):
            return fallback

    def _role_slot_total(self, role_ids):
        """Return configured max-player slots for the requested role IDs.

        Uses the live UI variables when available so the summary updates before
        the user generates/saves the blob. Negative values are treated as zero
        for display purposes; structural sanitization still happens on encode.
        """
        if not self.options:
            return 0
        total = 0
        for idx, role in enumerate(self.options.roles):
            if role.role_id not in role_ids:
                continue
            var = self.role_vars.get((idx, "max_players"))
            chance_var = self.role_vars.get((idx, "chance"))
            value = self._safe_var_int(var, role.max_players) if var is not None else role.max_players
            chance = self._safe_var_int(chance_var, role.chance) if chance_var is not None else role.chance
            if chance > 0:
                total += max(0, value)
        return total

    @staticmethod
    def _capacity_lines(title, population, configured_slots):
        """Return a clearer capacity summary for a living team.

        configured_slots is the sum of Max players for roles whose Chance is > 0.
        It describes possible role capacity, not guaranteed assignments.
        """
        population = max(0, population)
        configured_slots = max(0, configured_slots)
        possible_with_role = min(population, configured_slots)
        minimum_plain = max(0, population - configured_slots)
        excess = max(0, configured_slots - population)

        lines = [
            title,
            f"Team population: {population}",
            f"Configured role slots: {configured_slots}",
            f"Could receive a role: up to {possible_with_role} of {population}",
            f"Would remain plain if all available slots fill: at least {minimum_plain}",
        ]
        if excess:
            lines.append(f"Unused excess role slots: {excess}")
        return "\n".join(lines)

    def _update_role_capacity_summary(self):
        if not hasattr(self, "role_capacity_vars") or not self.options:
            return

        max_players_var = self.general_vars.get("max_players")
        impostors_var = self.general_vars.get("impostors")
        max_players = self._safe_var_int(max_players_var, self.options.max_players) if max_players_var else self.options.max_players
        impostor_max = self._safe_var_int(impostors_var, self.options.impostors) if impostors_var else self.options.impostors

        max_players = max(0, max_players)
        impostor_max = max(0, min(max_players, impostor_max))
        crew_max = max(0, max_players - impostor_max)

        living_crew_ids = {
            rid for rid in ROLE_NAMES
            if rid not in IMPOSTOR_ROLE_IDS and rid not in GHOST_CREWMATE_ROLE_IDS
        }
        crew_slots = self._role_slot_total(living_crew_ids)
        impostor_slots = self._role_slot_total(IMPOSTOR_ROLE_IDS)
        ghost_slots = self._role_slot_total(GHOST_CREWMATE_ROLE_IDS)

        crew_slots = max(0, crew_slots)
        crew_with_roles = min(crew_max, crew_slots)
        crew_excess_roles = max(0, crew_slots - crew_max)
        crew_without_roles = max(0, crew_max - crew_with_roles)
        self.role_capacity_vars["crew"].set(
            f"Maximum Population: {crew_max}\n"
            f"With Roles: {crew_with_roles}\n"
            f"Excess Roles: {crew_excess_roles}\n"
            f"Without Roles: {crew_without_roles}"
        )

        impostor_slots = max(0, impostor_slots)
        impostor_with_roles = min(impostor_max, impostor_slots)
        impostor_excess_roles = max(0, impostor_slots - impostor_max)
        impostor_without_roles = max(0, impostor_max - impostor_with_roles)
        self.role_capacity_vars["impostor"].set(
            f"Population: {impostor_max}\n"
            f"With Roles: {impostor_with_roles}\n"
            f"Excess Roles: {impostor_excess_roles}\n"
            f"Without Roles: {impostor_without_roles}"
        )

        # Classic-mode parity: Impostors win when living Crewmates <= living Impostors.
        # Therefore, with I living Impostors, at least I+1 Crewmates must still be alive
        # for the round to continue. Starting from crew_max Crewmates, the largest possible
        # number of Crewmate ghosts while the round is still active is crew_max-(I+1).
        for living_impostors in (1, 2, 3):
            ghost_max = max(0, crew_max - (living_impostors + 1))
            ghost_slots_available = max(0, ghost_slots)
            ghost_with_roles = min(ghost_max, ghost_slots_available)
            ghost_excess_roles = max(0, ghost_slots_available - ghost_max)
            ghost_without_roles = max(0, ghost_max - ghost_with_roles)
            self.role_capacity_vars[f"ghost{living_impostors}"].set(
                f"Maximum Population: {ghost_max}\n"
                f"With Roles: {ghost_with_roles}\n"
                f"Excess Roles: {ghost_excess_roles}\n"
                f"Without Roles: {ghost_without_roles}"
            )

    def _build_capacity_box(self, parent, title, variable, columns=1, column=0):
        box = ttk.LabelFrame(parent, text=title, padding=(8, 6))
        if columns == 1:
            box.pack(fill="x", padx=2, pady=(4, 8))
        else:
            box.grid(row=0, column=column, sticky="nsew", padx=4, pady=(4, 8))
            parent.columnconfigure(column, weight=1)
        ttk.Label(
            box, textvariable=variable, justify="left", anchor="nw"
        ).pack(anchor="nw", fill="x")
        return box

    def _build_roles(self):
        for child in self.roles_tab.inner.winfo_children():
            child.destroy()
        self.role_vars.clear()
        if not self.options:
            return

        p = self.roles_tab.inner
        ttk.Label(p, text="Role settings", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=6, pady=(8, 4))
        ttk.Label(
            p,
            text=("Living Crewmate roles, Crewmate Ghost roles, and Impostor roles are separated below. "
                  "Population counters show role capacity from the configured Max players values of roles with Chance > 0; "
                  "they do not guarantee that probabilistic roles will actually spawn."),
            foreground="#555",
            wraplength=940,
        ).pack(anchor="w", padx=6, pady=(0, 8))

        crew_banner = tk.Label(
            p, text="CREWMATE ROLES", bg="#2d7dd2", fg="white",
            font=("Segoe UI", 11, "bold"), padx=10, pady=6, anchor="w"
        )
        crew_banner.pack(fill="x", padx=6, pady=(6, 0))
        crew_section = ttk.Frame(p, padding=(2, 4, 2, 8))
        crew_section.pack(fill="x", padx=6, pady=(0, 10))
        self._build_capacity_box(crew_section, "Crewmate Population", self.role_capacity_vars["crew"])

        ghost_banner = tk.Label(
            p, text="CREWMATE GHOST ROLES", bg="#9ed8f0", fg="#15324a",
            font=("Segoe UI", 11, "bold"), padx=10, pady=6, anchor="w"
        )
        ghost_banner.pack(fill="x", padx=6, pady=(6, 0))
        ghost_section = ttk.Frame(p, padding=(2, 4, 2, 8))
        ghost_section.pack(fill="x", padx=6, pady=(0, 10))
        ghost_capacity_row = ttk.Frame(ghost_section)
        ghost_capacity_row.pack(fill="x", padx=2, pady=(0, 4))
        self._build_capacity_box(ghost_capacity_row, "1 Impostor", self.role_capacity_vars["ghost1"], columns=3, column=0)
        self._build_capacity_box(ghost_capacity_row, "2 Impostors", self.role_capacity_vars["ghost2"], columns=3, column=1)
        self._build_capacity_box(ghost_capacity_row, "3 Impostors", self.role_capacity_vars["ghost3"], columns=3, column=2)

        imp_banner = tk.Label(
            p, text="IMPOSTOR ROLES", bg="#b3261e", fg="white",
            font=("Segoe UI", 11, "bold"), padx=10, pady=6, anchor="w"
        )
        imp_banner.pack(fill="x", padx=6, pady=(6, 0))
        imp_section = ttk.Frame(p, padding=(2, 4, 2, 8))
        imp_section.pack(fill="x", padx=6, pady=(0, 10))
        self._build_capacity_box(imp_section, "Impostor Population", self.role_capacity_vars["impostor"])

        unknown_section = ttk.LabelFrame(p, text="Unknown / future roles", padding=4)

        unknown_used = False
        for idx, role in enumerate(self.options.roles):
            if role.role_id not in ROLE_NAMES:
                parent = unknown_section
                unknown_used = True
            elif role.role_id in IMPOSTOR_ROLE_IDS:
                parent = imp_section
            elif role.role_id in GHOST_CREWMATE_ROLE_IDS:
                parent = ghost_section
            else:
                parent = crew_section
            self._role_card(parent, idx, role)

        if unknown_used:
            unknown_section.pack(fill="x", padx=6, pady=(4, 8))

        self._update_role_capacity_summary()

    def _build_io(self):
        p = self.io_tab

        actions = ttk.LabelFrame(p, text="Import / Export actions", padding=8)
        actions.pack(fill="x")

        # Row 1: exporting the current options. settings.amogus load/save lives in
        # the persistent top bar above the notebook.
        ttk.Button(
            actions, text="Save normalHostOptions Base64 to file", command=self.save_blob_file
        ).grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        # Row 2: clipboard actions.
        ttk.Button(actions, text="Paste + Decode", command=self.paste_decode).grid(
            row=1, column=0, padx=4, pady=4, sticky="ew"
        )
        ttk.Button(actions, text="Generate + Copy", command=self.generate_copy).grid(
            row=1, column=1, padx=4, pady=4, sticky="ew"
        )

        # Row 3: file imports. The first expects settings.amogus-style JSON;
        # the second treats the file as plain text containing only the Base64 blob.
        ttk.Button(actions, text="Load from file…", command=self.load_settings_from_file).grid(
            row=2, column=0, padx=4, pady=4, sticky="ew"
        )
        ttk.Button(
            actions, text="Load plain Base64 from file…", command=self.load_blob_from_text_file
        ).grid(row=2, column=1, padx=4, pady=4, sticky="ew")

        for col in range(3):
            actions.columnconfigure(col, weight=1)

        ttk.Label(p, text="normalHostOptions Base64", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(14, 0)
        )
        self.blob_text = tk.Text(p, height=8, wrap="word")
        self.blob_text.pack(fill="x", pady=(5, 6))
        row = ttk.Frame(p)
        row.pack(fill="x")
        ttk.Button(row, text="Decode text above", command=self.decode_textbox).pack(side="left", padx=3)
        ttk.Button(row, text="Generate from controls", command=self.generate_to_textbox).pack(side="left", padx=3)
        ttk.Button(row, text="Copy", command=self.copy_textbox).pack(side="left", padx=3)
        ttk.Button(row, text="Paste", command=self.paste_to_textbox).pack(side="left", padx=3)

        ttk.Label(p, text="Sanitization / compatibility log", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(14, 3)
        )
        self.log_text = tk.Text(p, height=10, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _build_presets(self):
        p = self.presets_tab
        ttk.Label(p, text="Presets", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            p,
            text=("Presets store the complete generated normalHostOptions blob, including all role settings "
                  "and any unknown data preserved by the editor."),
            foreground="#555", wraplength=900,
        ).pack(anchor="w", pady=(3, 12))

        box = ttk.LabelFrame(p, text="Saved presets", padding=10)
        box.pack(fill="x")
        self.preset_combo = ttk.Combobox(box, textvariable=self.preset_var, state="readonly", width=42)
        self.preset_combo.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 10))
        ttk.Button(box, text="Load preset", command=self.load_preset).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(box, text="Save current as…", command=self.save_preset).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(box, text="Delete preset", command=self.delete_preset).grid(row=1, column=2, padx=4, pady=4, sticky="ew")
        for col in range(3):
            box.columnconfigure(col, weight=1)

    def _build_advanced(self):
        p = self.advanced_tab
        ttk.Label(p, text="Decoded structure", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.structure_text = tk.Text(p, wrap="none")
        self.structure_text.pack(fill="both", expand=True, pady=(5, 5))
        self.structure_text.configure(state="disabled")

    def _open_website(self, url: str):
        try:
            opened = webbrowser.open_new_tab(url)
            if not opened:
                messagebox.showwarning(APP_TITLE, f"Could not open this link automatically:\n{url}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open this link:\n{url}\n\n{exc}")

    def _build_credits(self):
        p = self.credits_tab
        ttk.Label(p, text="Credits", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            p,
            text="Project credits and related links.",
            foreground="#555", wraplength=900, justify="left",
        ).pack(anchor="w", pady=(3, 10))

        self.credits_text = tk.Text(p, height=16, wrap="word")
        self.credits_text.pack(fill="both", expand=True, pady=(0, 10))
        self.credits_text.insert("1.0", CREDIT_TEXT)
        self.credits_text.configure(state="disabled")

        links_box = ttk.LabelFrame(p, text="Links", padding=8)
        links_box.pack(fill="x")
        if CREDIT_LINKS:
            for label, url in CREDIT_LINKS:
                ttk.Button(
                    links_box,
                    text=label,
                    command=lambda target=url: self._open_website(target),
                ).pack(side="left", padx=(0, 6), pady=2)
        else:
            ttk.Label(links_box, text="No links configured.", foreground="#666").pack(anchor="w")

    def log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def load_blob(self, blob: str, quiet: bool = False) -> bool:
        try:
            decoded = NormalHostOptions.decode(blob)
            self.options = decoded
            self._populate_controls()
            self.blob_text.delete("1.0", "end")
            self.blob_text.insert("1.0", "".join(blob.split()))
            self._build_roles()
            self._update_structure()
            self.status.set(f"Decoded version {self.options.version}; {len(self.options.roles)} role records")
            if not quiet:
                self.log("Decoded normalHostOptions Base64 successfully.")
            return True
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not decode normalHostOptions:\n\n{e}")
            return False

    def _populate_controls(self):
        if not self.options:
            return
        for key, var in self.general_vars.items():
            if not hasattr(self.options, key):
                continue
            value = getattr(self.options, key)
            mapping = GENERAL_ENUMS.get(key)
            if mapping:
                if value in mapping:
                    var.set(self._enum_label(mapping, int(value)))
                else:
                    # Keep unsupported decoded values visible rather than hiding them.
                    var.set(f"Unknown ({value})")
            else:
                var.set(value)

    def _repair_or_raise_int(self, var, field_name: str, fallback: int, lo: int, hi: int) -> int:
        """Read an integer control, optionally repairing malformed/out-of-range input."""
        try:
            value = int(var.get())
        except (tk.TclError, ValueError, TypeError):
            if not self.prevent_invalid_values.get():
                raise ValueError(f"{field_name} must be an integer between {lo} and {hi}")
            value = int(fallback)
            self.log(f"Automatic adjustment: {field_name}: invalid input -> {value} (last valid value)")
            try:
                var.set(value)
            except tk.TclError:
                pass
            return value

        if value < lo or value > hi:
            if not self.prevent_invalid_values.get():
                raise ValueError(f"{field_name} must be between {lo} and {hi}; got {value}")
            repaired = max(lo, min(hi, value))
            self.log(f"Automatic adjustment: {field_name}: {value} -> {repaired} (code limit {lo}..{hi})")
            value = repaired
            try:
                var.set(value)
            except tk.TclError:
                pass
        return value

    def _repair_or_raise_float(self, var, field_name: str, fallback: float) -> float:
        """Read a float control and keep it within finite IEEE-754 float32 limits."""
        FLOAT32_MAX = 3.4028234663852886e38
        try:
            value = float(var.get())
        except (tk.TclError, ValueError, TypeError):
            if not self.prevent_invalid_values.get():
                raise ValueError(f"{field_name} must be a numeric value")
            value = float(fallback)
            self.log(f"Automatic adjustment: {field_name}: invalid input -> {value} (last valid value)")
            try:
                var.set(value)
            except tk.TclError:
                pass
            return value

        if not math.isfinite(value):
            if not self.prevent_invalid_values.get():
                raise ValueError(f"{field_name} must be a finite number")
            repaired = float(fallback) if math.isfinite(float(fallback)) else 0.0
            self.log(f"Automatic adjustment: {field_name}: non-finite -> {repaired} (last valid value)")
            value = repaired
        elif value > FLOAT32_MAX or value < -FLOAT32_MAX:
            if not self.prevent_invalid_values.get():
                raise ValueError(f"{field_name} exceeds the float32 code limit")
            repaired = max(-FLOAT32_MAX, min(FLOAT32_MAX, value))
            self.log(f"Automatic adjustment: {field_name}: {value} -> {repaired} (float32 code limit)")
            value = repaired

        try:
            var.set(value)
        except tk.TclError:
            pass
        return value

    def _general_int_limits(self):
        """Hard/serialization limits for editable integer fields."""
        return {
            "max_players": (4, 15),
            "common_tasks": (0, 255),
            "long_tasks": (0, 255),
            "short_tasks": (0, 255),
            "emergency_meetings": (-0x80000000, 0x7FFFFFFF),
            "impostors": (0, 255),
            "discussion_time": (-0x80000000, 0x7FFFFFFF),
            "voting_time": (-0x80000000, 0x7FFFFFFF),
            "emergency_cooldown": (0, 255),
        }

    def _commit_general_field(self, key: str):
        """Validate one General numeric field immediately after editing."""
        if not self.options or key not in self.general_vars:
            return
        try:
            var = self.general_vars[key]
            if key in self._general_int_limits():
                lo, hi = self._general_int_limits()[key]
                fallback = int(getattr(self.options, key))
                value = self._repair_or_raise_int(var, key.replace("_", " ").title(), fallback, lo, hi)
                setattr(self.options, key, value)
            elif key in {"player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"}:
                fallback = float(getattr(self.options, key))
                value = self._repair_or_raise_float(var, key.replace("_", " ").title(), fallback)
                if key == "kill_cooldown" and self.compat_guard.get() and value == 0.0:
                    value = 0.001
                    var.set(value)
                    self.log("Automatic adjustment: Kill Cooldown: 0 -> 0.001 (zero-cooldown compatibility guard)")
                setattr(self.options, key, value)
            self._update_role_capacity_summary()
            self._update_structure()
        except Exception as exc:
            # In strict mode, keep the user's text visible and report why it is invalid.
            self.status.set(f"Invalid value: {exc}")

    def _commit_role_field(self, idx: int, field: str):
        """Validate one role numeric field immediately after editing."""
        if not self.options or idx < 0 or idx >= len(self.options.roles):
            return
        role = self.options.roles[idx]
        try:
            if field == "max_players":
                var = self.role_vars[(idx, field)]
                role.max_players = self._repair_or_raise_int(var, f"{role.name} Max players", role.max_players, 0, 255)
            elif field == "chance":
                var = self.role_vars[(idx, field)]
                role.chance = self._repair_or_raise_int(var, f"{role.name} Chance", role.chance, 0, 255)
            elif field.startswith("payload_"):
                j = int(field.split("_", 1)[1])
                schema = ROLE_SCHEMAS.get(role.role_id)
                if not schema or j >= len(schema) or schema[j][1] == "bool":
                    return
                option_name = schema[j][0]
                var = self.role_vars[(idx, field)]
                fallback = role.payload[j] if j < len(role.payload) else 0
                value = self._repair_or_raise_int(var, f"{role.name} — {option_name}", fallback, 0, 255)
                role.set_option(j, schema[j][1], value)
            self._update_role_capacity_summary()
            self._update_structure()
        except Exception as exc:
            self.status.set(f"Invalid value: {exc}")

    def _validate_all_visible_fields(self):
        """Apply enabled safety guards immediately to all currently visible numeric fields."""
        if not self.options:
            return
        for key in list(self.general_vars):
            if key in self._general_int_limits() or key in {"player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"}:
                self._commit_general_field(key)
        for idx, role in enumerate(self.options.roles):
            self._commit_role_field(idx, "max_players")
            self._commit_role_field(idx, "chance")
            schema = ROLE_SCHEMAS.get(role.role_id)
            if schema:
                for j, (_, typ) in enumerate(schema):
                    if typ != "bool":
                        self._commit_role_field(idx, f"payload_{j}")

    def _sync_from_controls(self):
        if not self.options:
            raise ParseError("No options are loaded")

        # Visible integer fields and their actual serialized/code limits. These
        # are deliberately not the narrower limits used by the in-game menu.
        int_limits = self._general_int_limits()
        float_fields = {"player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"}
        bool_fields = {"confirm_ejects", "visual_tasks", "anonymous_votes"}

        for key, var in self.general_vars.items():
            if key in GENERAL_ENUMS:
                setattr(self.options, key, self._enum_value(GENERAL_ENUMS[key], str(var.get())))
            elif key in int_limits:
                lo, hi = int_limits[key]
                current = int(getattr(self.options, key))
                value = self._repair_or_raise_int(var, key.replace("_", " ").title(), current, lo, hi)
                setattr(self.options, key, value)
            elif key in float_fields:
                current = float(getattr(self.options, key))
                value = self._repair_or_raise_float(var, key.replace("_", " ").title(), current)
                setattr(self.options, key, value)
            elif key in bool_fields:
                setattr(self.options, key, bool(var.get()))

        for idx, role in enumerate(self.options.roles):
            role.max_players = self._repair_or_raise_int(
                self.role_vars[(idx, "max_players")],
                f"{role.name} Max players", role.max_players, 0, 255
            )
            role.chance = self._repair_or_raise_int(
                self.role_vars[(idx, "chance")],
                f"{role.name} Chance", role.chance, 0, 255
            )
            schema = ROLE_SCHEMAS.get(role.role_id)
            if schema:
                for j, (option_name, typ) in enumerate(schema):
                    var = self.role_vars[(idx, f"payload_{j}")]
                    if typ == "bool":
                        role.set_option(j, typ, bool(var.get()))
                    else:
                        fallback = role.payload[j] if j < len(role.payload) else 0
                        value = self._repair_or_raise_int(
                            var, f"{role.name} — {option_name}", fallback, 0, 255
                        )
                        role.set_option(j, typ, value)
            else:
                raw = str(self.role_vars[(idx, "raw_payload")].get()).replace(" ", "")
                if len(raw) % 2:
                    raise ValueError(f"{role.name}: raw payload hex must have an even number of digits")
                try:
                    role.payload = bytearray.fromhex(raw)
                except ValueError as exc:
                    raise ValueError(f"{role.name}: raw payload must contain hexadecimal bytes only") from exc

    def _update_structure(self):
        if not self.options:
            return
        d = {
            "version": self.options.version,
            "outer_tag": self.options.outer_tag,
            "game_mode": {"id": self.options.game_mode, "name": GAME_MODE_NAMES.get(self.options.game_mode, "unknown")},
            "special_mode": self.options.special_mode,
            "rules_preset": self.options.rules_preset,
            "max_players": self.options.max_players,
            "keywords": self.options.keywords,
            "map": {"id": self.options.map_id, "name": MAP_NAMES.get(self.options.map_id, "unknown")},
            "player_speed": self.options.player_speed,
            "crewmate_vision": self.options.crewmate_vision,
            "impostor_vision": self.options.impostor_vision,
            "kill_cooldown": self.options.kill_cooldown,
            "tasks": {"common": self.options.common_tasks, "long": self.options.long_tasks, "short": self.options.short_tasks},
            "emergency_meetings": self.options.emergency_meetings,
            "impostors": self.options.impostors,
            "kill_distance": {"id": self.options.kill_distance, "name": KILL_DISTANCE_NAMES.get(self.options.kill_distance, "unknown")},
            "discussion_time": self.options.discussion_time,
            "voting_time": self.options.voting_time,
            "is_defaults": self.options.is_defaults,
            "emergency_cooldown": self.options.emergency_cooldown,
            "confirm_ejects": self.options.confirm_ejects,
            "visual_tasks": self.options.visual_tasks,
            "anonymous_votes": self.options.anonymous_votes,
            "taskbar_updates": {"id": self.options.taskbar_updates, "name": TASKBAR_NAMES.get(self.options.taskbar_updates, "unknown")},
            "tag": self.options.tag,
            "roles": [
                {
                    "role_id": r.role_id,
                    "name": r.name,
                    "team": ("Impostor" if r.role_id in IMPOSTOR_ROLE_IDS else "Crewmate Ghost" if r.role_id in GHOST_CREWMATE_ROLE_IDS else "Crewmate"),
                    "max_players": r.max_players,
                    "chance": r.chance,
                    "message_tag": r.message_tag,
                    "options": r.decoded_options(),
                    "raw_payload_hex": r.payload.hex(" "),
                } for r in self.options.roles
            ],
            "payload_trailing_bytes_hex": self.options.payload_trailing_bytes.hex(" "),
            "outer_trailing_bytes_hex": self.options.outer_trailing_bytes.hex(" "),
        }
        self.structure_text.configure(state="normal")
        self.structure_text.delete("1.0", "end")
        self.structure_text.insert("1.0", json.dumps(d, indent=2, ensure_ascii=False))
        self.structure_text.configure(state="disabled")

    def generate(self) -> str:
        self._sync_from_controls()
        blob, changes = self.options.encode(self.compat_guard.get(), self.prevent_invalid_values.get())
        if changes:
            for change in changes:
                self.log(f"Automatic adjustment during generation: {change}")
            self._populate_controls()
            self._build_roles()
        self._update_structure()
        return blob

    def generate_to_textbox(self):
        try:
            blob = self.generate()
            self.blob_text.delete("1.0", "end")
            self.blob_text.insert("1.0", blob)
            self.status.set("Generated normalHostOptions")
            self.log("Generated normalHostOptions Base64 into the text box.")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not generate options:\n\n{e}")

    def generate_copy(self):
        try:
            blob = self.generate()
            self.clipboard_clear()
            self.clipboard_append(blob)
            self.update()
            self.blob_text.delete("1.0", "end")
            self.blob_text.insert("1.0", blob)
            self.status.set("Generated and copied to clipboard")
            self.log("Generated normalHostOptions Base64 and copied it to the clipboard.")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not generate options:\n\n{e}")

    def paste_decode(self):
        try:
            blob = self.clipboard_get()
        except tk.TclError:
            messagebox.showerror(APP_TITLE, "Clipboard does not contain text")
            return
        if self.load_blob(blob, quiet=True):
            self.log("Pasted Base64 from the clipboard and decoded it successfully.")

    def paste_to_textbox(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self.blob_text.delete("1.0", "end")
        self.blob_text.insert("1.0", text)
        self.log("Pasted clipboard text into the Base64 text box (not decoded).")

    def copy_textbox(self):
        text = self.blob_text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status.set("Copied Base64")
        self.log("Copied the Base64 text box contents to the clipboard.")

    def decode_textbox(self):
        if self.load_blob(self.blob_text.get("1.0", "end").strip(), quiet=True):
            self.log("Decoded normalHostOptions Base64 from the text box successfully.")

    def _load_settings_path(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            blob = data["multiplayer"]["normalHostOptions"]
        except (KeyError, TypeError) as e:
            raise KeyError("multiplayer.normalHostOptions was not found in this file") from e
        if not isinstance(blob, str):
            raise TypeError("multiplayer.normalHostOptions is not a string")
        if not self.load_blob(blob, quiet=True):
            raise ParseError("The file contains an invalid or unsupported normalHostOptions value")
        self.loaded_settings_path = path
        self.log(f"Loaded multiplayer.normalHostOptions from {path}")
        self.status.set(f"Loaded {path}")

    def load_default_settings(self):
        path = DEFAULT_SETTINGS_PATH
        if not path.exists():
            messagebox.showerror(APP_TITLE, f"Default settings.amogus was not found at:\n\n{path}\n\nUse 'Load from file…' instead.")
            return
        try:
            self._load_settings_path(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not load settings.amogus:\n\n{e}")

    def load_settings_from_file(self):
        chosen = filedialog.askopenfilename(
            title="Load Among Us settings-formatted file",
            filetypes=[("Among Us settings / JSON", "*.amogus *.json"), ("All files", "*.*")],
        )
        if not chosen:
            return
        try:
            self._load_settings_path(Path(chosen))
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not load settings-formatted file:\n\n{e}")

    def load_blob_from_text_file(self):
        chosen = filedialog.askopenfilename(
            title="Load plain normalHostOptions Base64 file",
            filetypes=[("Text files", "*.txt *.b64 *.base64"), ("All files", "*.*")],
        )
        if not chosen:
            return
        try:
            text = Path(chosen).read_text(encoding="utf-8").strip()
            if not text:
                raise ValueError("The selected file is empty")
            if not self.load_blob(text, quiet=True):
                return
            self.log(f"Loaded plain normalHostOptions Base64 from {chosen}")
            self.status.set(f"Loaded Base64 from {chosen}")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not load plain Base64 file:\n\n{e}")

    def save_to_settings(self):
        try:
            blob = self.generate()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not generate options:\n\n{e}")
            return

        path = DEFAULT_SETTINGS_PATH
        if not path.exists():
            chosen = filedialog.askopenfilename(
                title="Select settings.amogus to modify",
                filetypes=[("Among Us settings", "*.amogus"), ("All files", "*.*")],
            )
            if not chosen:
                return
            path = Path(chosen)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "multiplayer" not in data or not isinstance(data["multiplayer"], dict):
                raise KeyError("multiplayer object was not found")
            if "normalHostOptions" not in data["multiplayer"]:
                raise KeyError("multiplayer.normalHostOptions was not found")

            backup = path.with_name(path.name + ".backup")
            shutil.copy2(path, backup)
            data["multiplayer"]["normalHostOptions"] = blob
            path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
            self.log(f"Backup created: {backup}")
            self.log(f"Saved normalHostOptions to: {path}")
            self.status.set("Saved to settings.amogus (backup created)")
            messagebox.showinfo(
                APP_TITLE,
                "Saved successfully.\n\nA backup was created. Close Among Us before saving or the game may overwrite the file on exit.",
            )
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not modify settings.amogus:\n\n{e}")

    def save_blob_file(self):
        try:
            blob = self.generate()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(blob + "\n", encoding="utf-8")
        self.status.set(f"Saved {path}")
        self.log(f"Saved normalHostOptions Base64 to file: {path}")

    def _initialize_first_run_presets(self):
        """Create the built-in Chaos preset only for a fresh preset store.

        Existing preset files are left untouched, so user-created presets and
        an intentionally modified/deleted Chaos preset are never overwritten.
        """
        if PRESETS_PATH.exists():
            return
        try:
            self._write_presets({DEFAULT_PRESET_NAME: DEFAULT_BLOB})
        except Exception as e:
            # Presets are optional; startup should still succeed if the app
            # cannot create its local preset file.
            self.log(f"Could not create first-run preset '{DEFAULT_PRESET_NAME}': {e}")

    def _read_presets(self) -> Dict[str, str]:
        if not PRESETS_PATH.exists():
            return {}
        try:
            data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}

    def _write_presets(self, presets: Dict[str, str]):
        PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRESETS_PATH.write_text(json.dumps(presets, indent=4, ensure_ascii=False), encoding="utf-8")

    def _refresh_presets(self):
        if not hasattr(self, "preset_combo"):
            return
        names = sorted(self._read_presets(), key=str.casefold)
        self.preset_combo["values"] = names
        if self.preset_var.get() not in names:
            self.preset_var.set(names[0] if names else "")

    def save_preset(self):
        try:
            blob = self.generate()
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not create preset:\n\n{e}")
            return
        name = simpledialog.askstring(APP_TITLE, "Preset name:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        presets = self._read_presets()
        if name in presets and not messagebox.askyesno(APP_TITLE, f"Preset '{name}' already exists. Replace it?"):
            return
        presets[name] = blob
        try:
            self._write_presets(presets)
            self._refresh_presets()
            self.preset_var.set(name)
            self.log(f"Saved preset: {name}")
            self.status.set(f"Preset saved: {name}")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not save preset:\n\n{e}")

    def load_preset(self):
        name = self.preset_var.get().strip()
        if not name:
            messagebox.showinfo(APP_TITLE, "No preset is selected.")
            return
        presets = self._read_presets()
        blob = presets.get(name)
        if not blob:
            messagebox.showerror(APP_TITLE, f"Preset '{name}' was not found.")
            self._refresh_presets()
            return
        if not self.load_blob(blob, quiet=True):
            return
        self.log(f"Loaded preset: {name}")
        self.status.set(f"Preset loaded: {name}")

    def delete_preset(self):
        name = self.preset_var.get().strip()
        if not name:
            return
        if not messagebox.askyesno(APP_TITLE, f"Delete preset '{name}'?"):
            return
        presets = self._read_presets()
        presets.pop(name, None)
        try:
            self._write_presets(presets)
            self._refresh_presets()
            self.log(f"Deleted preset: {name}")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not delete preset:\n\n{e}")


if __name__ == "__main__":
    App().mainloop()
