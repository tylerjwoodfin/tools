#!/usr/bin/env python3
"""Build the two Shortcuts that drive early bedtime.

Early Bedtime Check sends last night's Apple Health sleep to cloud, which saves
the time asleep and returns it for a notification.
Early Bedtime Do Not Disturb asks cloud whether today is armed, and turns
Do Not Disturb on only when the answer is early.

Personal automations are stored on the iPhone, so the shortcut files do not
include the 12:00pm and 8:30pm schedules. Those are created once in the
Shortcuts app. See bedtime/README.md.

The Shortcuts app only imports signed files. On a Mac, this script signs with
``shortcuts sign --mode people-who-know-me``, which stays on the Mac and
imports on your devices. The ``anyone`` mode would send a copy to Apple.
"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_PATH = ROOT / "Early Bedtime Check.shortcut"
DND_PATH = ROOT / "Early Bedtime Do Not Disturb.shortcut"

CLOUD_HOST = "192.168.1.101"
CLOUD_PORT = "62561"
CLOUD_USER = "tyler"
SCRIPT = '/usr/bin/python3 "$HOME/git/tools/bedtime/early_bedtime.py"'

FIND = "4B1C0A11-4480-4E11-9C10-000000000001"
CHECK_SSH = "4B1C0A11-4480-4E11-9C10-00000000000A"
DND_SSH = "4B1C0A11-4480-4E11-9C10-00000000000B"
DND_GROUP = "4B1C0A11-4480-4E11-9C10-00000000000C"

MARKER = "\ufffc"
DAYS = 16  # NSCalendarUnitDay. 16384 is week-based years.


def _action(identifier: str, **params: object) -> dict:
    return {
        "WFWorkflowActionIdentifier": identifier,
        "WFWorkflowActionParameters": params,
    }


def _output(uuid: str, name: str) -> dict:
    return {
        "Value": {"OutputUUID": uuid, "OutputName": name, "Type": "ActionOutput"},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def _text(body: str, attachments: dict) -> dict:
    return {
        "Value": {"string": body, "attachmentsByRange": attachments},
        "WFSerializationType": "WFTextTokenString",
    }


def _property(name: str, *formats: dict) -> dict:
    """One property of every sample found. A list becomes one item per line."""
    return {
        "OutputUUID": FIND,
        "OutputName": "Health Samples",
        "Type": "ActionOutput",
        "Aggrandizements": [
            {"Type": "WFPropertyVariableAggrandizement", "PropertyName": name},
            *formats,
        ],
    }


def check_ssh_script() -> dict:
    """Remote command carrying three lists, so the phone needs no loop."""
    iso_time = {
        "Type": "WFDateFormatVariableAggrandizement",
        "WFDateFormatStyle": "ISO 8601",
        "WFISO8601IncludeTime": True,
    }
    body = SCRIPT + " check <<'EARLY_BEDTIME_END'\n"
    attachments = {}
    for header, token in (
        ("VALUES", _property("Value")),
        ("STARTS", _property("Start Date", iso_time)),
        ("ENDS", _property("End Date", iso_time)),
    ):
        body += header + "\n"
        attachments[f"{{{len(body)}, 1}}"] = token
        body += MARKER + "\n"
    return _text(body + "EARLY_BEDTIME_END\n", attachments)


def _ssh(uuid: str, script) -> dict:
    return _action(
        "is.workflow.actions.runsshscript",
        UUID=uuid,
        WFSSHHost=CLOUD_HOST,
        WFSSHPort=CLOUD_PORT,
        WFSSHUser=CLOUD_USER,
        WFSSHAuthenticationType="SSH Key",
        WFSSHScript=script,
    )


def _health_filter() -> dict:
    return {
        "Value": {
            "WFActionParameterFilterPrefix": 1,
            "WFContentPredicateBoundedDate": False,
            "WFActionParameterFilterTemplates": [
                {
                    "Bounded": True,
                    "Operator": 4,
                    "Property": "Type",
                    "Removable": False,
                    "Values": {
                        "Enumeration": {
                            "Value": "Sleep",
                            "WFSerializationType": "WFStringSubstitutableState",
                        }
                    },
                },
                {
                    "Bounded": True,
                    "Operator": 1001,
                    "Property": "Start Date",
                    "Removable": True,
                    "Values": {"Number": 1, "Unit": DAYS},
                },
            ],
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }


def check_workflow() -> dict:
    """Find last night, send it to cloud, show the duration that came back."""
    actions = [
        _action(
            "is.workflow.actions.filter.health.quantity",
            UUID=FIND,
            WFContentItemFilter=_health_filter(),
        ),
        _ssh(CHECK_SSH, check_ssh_script()),
        _action(
            "is.workflow.actions.notification",
            WFNotificationActionTitle="Early Bedtime",
            WFNotificationActionBody=_text(
                MARKER,
                {
                    "{0, 1}": {
                        "OutputUUID": CHECK_SSH,
                        "OutputName": "Shell Script Result",
                        "Type": "ActionOutput",
                    }
                },
            ),
        ),
    ]
    return _workflow("Early Bedtime Check", actions)


def dnd_workflow() -> dict:
    """Shortcut run by an 8:30pm personal automation."""
    actions = [
        _action(
            "is.workflow.actions.comment",
            WFCommentActionText=(
                "Automation: every day at 8:30pm, run immediately. "
                "Turns on Do Not Disturb only when early bedtime is armed."
            ),
        ),
        _ssh(DND_SSH, SCRIPT + " status"),
        _action(
            "is.workflow.actions.conditional",
            GroupingIdentifier=DND_GROUP,
            WFControlFlowMode=0,
            WFCondition="Contains",
            WFConditionalActionString="early",
            WFInput=_output(DND_SSH, "Shell Script Result"),
        ),
        _action(
            "is.workflow.actions.dnd.set",
            Enabled=True,
            Operation="Turn",
        ),
        _action(
            "is.workflow.actions.conditional",
            GroupingIdentifier=DND_GROUP,
            WFControlFlowMode=1,
        ),
        _action(
            "is.workflow.actions.conditional",
            GroupingIdentifier=DND_GROUP,
            WFControlFlowMode=2,
        ),
    ]
    return _workflow("Early Bedtime Do Not Disturb", actions)


def _workflow(name: str, actions: list[dict]) -> dict:
    return {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "2705.1.0",
        "WFWorkflowClientRelease": "27.0",
        "WFWorkflowName": name,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59511,
            "WFWorkflowIconStartColor": 431817727,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem"],
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowActions": actions,
    }


def write_shortcuts(directory: Path | None = None) -> tuple[Path, Path]:
    """Write both unsigned shortcut plists. Returns the check path and the DND path."""
    folder = directory or ROOT
    check_path = folder / CHECK_PATH.name
    dnd_path = folder / DND_PATH.name
    for path, workflow in (
        (check_path, check_workflow()),
        (dnd_path, dnd_workflow()),
    ):
        with path.open("wb") as handle:
            plistlib.dump(workflow, handle, fmt=plistlib.FMT_XML, sort_keys=False)
    return check_path, dnd_path


def sign_file(path: Path) -> Path:
    """Replace an unsigned shortcut plist with a signed file. Mac only.

    The output keeps ``path``'s filename, which is the name Shortcuts uses on
    import. Signing uses ``people-who-know-me`` so the file stays local.
    """
    if sys.platform != "darwin":
        raise OSError("The shortcuts CLI can sign files only on macOS")
    binary = shutil.which("shortcuts")
    if binary is None:
        raise OSError("The shortcuts CLI is not installed")

    workflow = plistlib.loads(path.read_bytes())
    # `shortcuts sign` rejects input whose name does not end in .shortcut.
    unsigned = path.with_name(f"{path.stem}.unsigned.shortcut")
    backup = path.with_name(f".{path.name}.backup")
    with unsigned.open("wb") as handle:
        plistlib.dump(workflow, handle, fmt=plistlib.FMT_BINARY)
    path.replace(backup)
    try:
        subprocess.run(
            [
                binary,
                "sign",
                "--mode",
                "people-who-know-me",
                "--input",
                str(unsigned),
                "--output",
                str(path),
            ],
            check=True,
        )
    except Exception:
        if not path.exists():
            backup.replace(path)
        raise
    else:
        backup.unlink(missing_ok=True)
    finally:
        unsigned.unlink(missing_ok=True)
    return path


def sign_shortcuts(paths: tuple[Path, Path]) -> tuple[Path, Path]:
    """Sign both shortcuts in place. Returns the same paths."""
    for path in paths:
        sign_file(path)
    return paths


def main() -> None:
    paths = write_shortcuts()
    for path in paths:
        print(path)
    if sys.platform == "darwin" and shutil.which("shortcuts"):
        sign_shortcuts(paths)
        return
    print(
        "These files are unsigned, so the Shortcuts app will not import them.\n"
        "On the Mac, from this directory, run: python3 shortcuts.py",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
