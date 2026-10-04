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
# Edit this text however you like. It is shown in the Credits tab and remains
# editable at runtime. Use CREDIT_LINKS below for clickable website buttons.
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

# A v19-format Normal options blob used only as a convenient starter.
DEFAULT_BLOB = (
    "DJQAAAEAZA8AAQAAAAAA4D8AAABAAAAAQG8SgzoBAQEDAAAAAQAeAAAAHgAAAAAKAQEBAAALBQABZAMAAAABAAIAAmQCAAAA/wQAAWQDAAAAgAEDAANkAgAAAP8JAAFkAgAAAP8KAAJkAwAAAP8BCAAEZAIAAP8BDAACZAEAAAQSAAFkAQAAChMAAmQBAAAAFQADZAEAAAA="
)

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

    def sanitize(self, compatibility_guard: bool = True) -> List[str]:
        """Clamp only values that are certainly incompatible with their serialized type,
        plus one optional compatibility guard: Kill Cooldown == 0 can disable killing
        in some current builds, so the guard substitutes a tiny positive float.

        We DO NOT clamp role durations/cooldowns to normal UI ranges, because custom
        byte values (including 0/128/255) are intentionally part of this editor's purpose.
        """
        changes = []

        # hard serialized-type constraints
        for attr in (
            "game_mode", "special_mode", "rules_preset", "max_players", "map_id",
            "common_tasks", "long_tasks", "short_tasks", "impostors", "kill_distance",
            "emergency_cooldown", "taskbar_updates", "tag"
        ):
            old = int(getattr(self, attr))
            new, changed = clamp_int(old, 0, 255)
            if changed:
                setattr(self, attr, new)
                changes.append(f"{attr}: {old} -> {new} (uint8 limit)")

        old_kw = int(self.keywords)
        self.keywords = max(0, min(0xFFFFFFFF, old_kw))
        if self.keywords != old_kw:
            changes.append(f"keywords: {old_kw} -> {self.keywords} (uint32 limit)")

        for attr in ("emergency_meetings", "discussion_time", "voting_time"):
            old = int(getattr(self, attr))
            new = max(-0x80000000, min(0x7FFFFFFF, old))
            if new != old:
                setattr(self, attr, new)
                changes.append(f"{attr}: {old} -> {new} (int32 limit)")

        for attr in ("player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"):
            old = float(getattr(self, attr))
            new, changed = finite_float(old, 0.0)
            if changed:
                setattr(self, attr, new)
                changes.append(f"{attr}: non-finite -> 0.0")

        # Strong protocol validity limits for role quantity/chance.
        for role in self.roles:
            old = role.max_players
            role.max_players, changed = clamp_int(int(role.max_players), 0, 15)
            if changed:
                changes.append(f"{role.name} max players: {old} -> {role.max_players}")
            old = role.chance
            role.chance, changed = clamp_int(int(role.chance), 0, 100)
            if changed:
                changes.append(f"{role.name} chance: {old} -> {role.chance}")
            for i in range(len(role.payload)):
                # bytearray already guarantees 0..255, retained for documentation.
                role.payload[i] &= 0xFF

        # Compatibility safeguard: exact-zero kill cooldown can disable kills in some builds.
        if compatibility_guard and self.kill_cooldown <= 0:
            old = self.kill_cooldown
            self.kill_cooldown = 0.001
            changes.append(f"kill_cooldown: {old} -> 0.001 (compatibility guard for exact-zero kill cooldown)")

        return changes

    def encode(self, compatibility_guard: bool = True) -> Tuple[str, List[str]]:
        changes = self.sanitize(compatibility_guard)

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
        self.status = tk.StringVar(value="Ready")
        self.preset_var = tk.StringVar()
        self.loaded_settings_path: Path | None = None
        self.role_capacity_vars = {
            "crew": tk.StringVar(value="Living Crewmates: —"),
            "impostor": tk.StringVar(value="Impostors: —"),
            "ghost": tk.StringVar(value="Crewmate Ghosts: —"),
        }
        self._build_ui()
        self.load_blob(DEFAULT_BLOB, quiet=True)
        self._refresh_presets()

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
        ttk.Checkbutton(
            top,
            text="Protect kill cooldown from exact 0",
            variable=self.compat_guard,
        ).pack(side="right")

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
            note="Maximum lobby size. Official Among Us lobbies support 4–15 players; the serialized field itself is one byte."
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
        ttk.Entry(box, textvariable=max_var, width=10).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(box, text="Chance %").grid(row=0, column=2, sticky="w", padx=(18, 4))
        ttk.Entry(box, textvariable=chance_var, width=10).grid(row=0, column=3, sticky="w", padx=4)

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
                    ttk.Entry(box, textvariable=var, width=10).grid(row=row, column=1, sticky="w", padx=4)
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
    def _capacity_text(label, population, configured_slots):
        population = max(0, population)
        configured_slots = max(0, configured_slots)
        with_role = min(population, configured_slots)
        without_role = max(0, population - with_role)
        excess = max(0, configured_slots - population)
        text = f"{label}: {with_role} with role  •  {without_role} without role  •  max population {population}"
        if excess:
            text += f"  •  {excess} excess configured role slot{'s' if excess != 1 else ''}"
        return text

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

        living_crew_ids = {rid for rid in ROLE_NAMES if rid not in IMPOSTOR_ROLE_IDS and rid not in GHOST_CREWMATE_ROLE_IDS}
        crew_slots = self._role_slot_total(living_crew_ids)
        impostor_slots = self._role_slot_total(IMPOSTOR_ROLE_IDS)
        ghost_slots = self._role_slot_total(GHOST_CREWMATE_ROLE_IDS)

        # In Classic mode, Impostors win at parity: living Crewmates <= living
        # Impostors. The editor cannot know how many Impostors will still be alive
        # later in a round, so show both useful bounds:
        #   - start-state bound: all configured Impostors are still alive;
        #   - absolute active-round bound: only one Impostor remains alive.
        ghost_max_start = max(0, crew_max - (impostor_max + 1)) if impostor_max else 0
        ghost_max_theoretical = max(0, crew_max - 2) if impostor_max else 0

        self.role_capacity_vars["crew"].set(
            self._capacity_text("Living Crewmates", crew_max, crew_slots)
        )
        self.role_capacity_vars["impostor"].set(
            self._capacity_text("Impostors", impostor_max, impostor_slots)
        )
        ghost_population = ghost_max_theoretical
        base = self._capacity_text("Crewmate Ghosts", ghost_population, ghost_slots)
        if impostor_max > 1:
            base += f"  •  max with all {impostor_max} Impostors alive: {ghost_max_start}"
        self.role_capacity_vars["ghost"].set(base)

    def _build_role_capacity_panel(self, parent):
        panel = ttk.LabelFrame(parent, text="Automatic role capacity", padding=(10, 8))
        panel.pack(fill="x", padx=6, pady=(0, 10))

        ttk.Label(
            panel,
            textvariable=self.role_capacity_vars["crew"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=2)
        ttk.Label(
            panel,
            textvariable=self.role_capacity_vars["impostor"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=2)
        ttk.Label(
            panel,
            textvariable=self.role_capacity_vars["ghost"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=2)
        ttk.Label(
            panel,
            text=("Read-only. Counts use each role's configured Max players. Classic mode ends at parity "
                  "(living Crewmates ≤ living Impostors). The displayed Crewmate Ghost maximum is the "
                  "largest population possible while a round is still active if only one Impostor remains; "
                  "when multiple Impostors are configured, the stricter all-Impostors-alive bound is also shown. "
                  "Roles at 0% chance are excluded. If a role chance is between 1% and 99%, these are potential "
                  "capacity/slot counts rather than guaranteed assignments."),
            foreground="#666", wraplength=920, justify="left",
        ).pack(anchor="w", pady=(5, 0))

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
            text=("Crewmate-team and Impostor-team roles are separated below. Custom byte values 0–255 remain allowed; "
                  "the editor only clamps values that are structurally invalid."),
            foreground="#555",
            wraplength=940,
        ).pack(anchor="w", padx=6, pady=(0, 8))

        self._build_role_capacity_panel(p)

        crew_banner = tk.Label(
            p, text="CREWMATE ROLES", bg="#2d7dd2", fg="white",
            font=("Segoe UI", 11, "bold"), padx=10, pady=6, anchor="w"
        )
        crew_banner.pack(fill="x", padx=6, pady=(6, 0))
        crew_section = ttk.Frame(p, padding=(2, 4, 2, 8))
        crew_section.pack(fill="x", padx=6, pady=(0, 10))

        imp_banner = tk.Label(
            p, text="IMPOSTOR ROLES", bg="#b3261e", fg="white",
            font=("Segoe UI", 11, "bold"), padx=10, pady=6, anchor="w"
        )
        imp_banner.pack(fill="x", padx=6, pady=(6, 0))
        imp_section = ttk.Frame(p, padding=(2, 4, 2, 8))
        imp_section.pack(fill="x", padx=6, pady=(0, 10))

        unknown_section = ttk.LabelFrame(p, text="Unknown / future roles", padding=4)

        unknown_used = False
        for idx, role in enumerate(self.options.roles):
            if role.role_id not in ROLE_NAMES:
                parent = unknown_section
                unknown_used = True
            elif role.role_id in IMPOSTOR_ROLE_IDS:
                parent = imp_section
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
            text=("The text below is an editable template. To change the default text permanently, edit "
                  "CREDIT_TEXT near the top of this .pyw file. Clickable links are defined in CREDIT_LINKS."),
            foreground="#555", wraplength=900, justify="left",
        ).pack(anchor="w", pady=(3, 10))

        self.credits_text = tk.Text(p, height=16, wrap="word")
        self.credits_text.pack(fill="both", expand=True, pady=(0, 10))
        self.credits_text.insert("1.0", CREDIT_TEXT)

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
                self.log("Decoded Base64 successfully.")
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

    def _sync_from_controls(self):
        if not self.options:
            raise ParseError("No options are loaded")

        int_fields = {
            "version", "max_players", "common_tasks", "long_tasks", "short_tasks",
            "emergency_meetings", "impostors", "discussion_time", "voting_time",
            "emergency_cooldown", "special_mode", "rules_preset", "keywords", "tag"
        }
        float_fields = {"player_speed", "crewmate_vision", "impostor_vision", "kill_cooldown"}
        bool_fields = {"confirm_ejects", "visual_tasks", "anonymous_votes", "is_defaults"}

        for key, var in self.general_vars.items():
            if key in GENERAL_ENUMS:
                setattr(self.options, key, self._enum_value(GENERAL_ENUMS[key], str(var.get())))
            elif key in int_fields:
                setattr(self.options, key, int(var.get()))
            elif key in float_fields:
                setattr(self.options, key, float(var.get()))
            elif key in bool_fields:
                setattr(self.options, key, bool(var.get()))

        for idx, role in enumerate(self.options.roles):
            role.max_players = int(self.role_vars[(idx, "max_players")].get())
            role.chance = int(self.role_vars[(idx, "chance")].get())
            schema = ROLE_SCHEMAS.get(role.role_id)
            if schema:
                for j, (_, typ) in enumerate(schema):
                    var = self.role_vars[(idx, f"payload_{j}")]
                    value = bool(var.get()) if typ == "bool" else int(var.get())
                    role.set_option(j, typ, value)
            else:
                raw = str(self.role_vars[(idx, "raw_payload")].get()).replace(" ", "")
                if len(raw) % 2:
                    raise ValueError(f"{role.name}: raw payload hex must have an even number of digits")
                role.payload = bytearray.fromhex(raw)

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
        blob, changes = self.options.encode(self.compat_guard.get())
        if changes:
            self.log("Automatic adjustments:")
            for change in changes:
                self.log(f"  - {change}")
            self._populate_controls()
            self._build_roles()
        else:
            self.log("Generated with no automatic adjustments.")
        self._update_structure()
        return blob

    def generate_to_textbox(self):
        try:
            blob = self.generate()
            self.blob_text.delete("1.0", "end")
            self.blob_text.insert("1.0", blob)
            self.status.set("Generated normalHostOptions")
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
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not generate options:\n\n{e}")

    def paste_decode(self):
        try:
            blob = self.clipboard_get()
        except tk.TclError:
            messagebox.showerror(APP_TITLE, "Clipboard does not contain text")
            return
        self.load_blob(blob)

    def paste_to_textbox(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self.blob_text.delete("1.0", "end")
        self.blob_text.insert("1.0", text)

    def copy_textbox(self):
        text = self.blob_text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status.set("Copied Base64")

    def decode_textbox(self):
        self.load_blob(self.blob_text.get("1.0", "end").strip())

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
