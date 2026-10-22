#!/usr/bin/env python3
"""Build the two Shortcuts that drive early bedtime.

Early Bedtime Check reads Apple Health sleep and SSHes the rows to cloud.
Early Bedtime Do Not Disturb asks cloud whether today is armed, and turns
Do Not Disturb on only when the answer is early.

Personal automations are stored on the iPhone, so the shortcut files do not
include the 12:00pm and 8:30pm schedules. Those are created once in the
Shortcuts app. See bedtime/README.md.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_PATH = ROOT / "Early Bedtime Check.shortcut"
DND_PATH = ROOT / "Early Bedtime Do Not Disturb.shortcut"

CLOUD_HOST = "192.168.1.101"
CLOUD_PORT = "62561"
CLOUD_USER = "tyler"
SCRIPT = '/usr/bin/python3 "$HOME/git/tools/bedtime/early_bedtime.py"'

FIND = "4B1C0A11-4480-4E11-9C10-000000000001"
REPEAT_GROUP = "4B1C0A11-4480-4E11-9C10-000000000002"
DETAIL_VALUE = "4B1C0A11-4480-4E11-9C10-000000000003"
DETAIL_START = "4B1C0A11-4480-4E11-9C10-000000000004"
DETAIL_END = "4B1C0A11-4480-4E11-9C10-000000000005"
FORMAT_START = "4B1C0A11-4480-4E11-9C10-000000000006"
FORMAT_END = "4B1C0A11-4480-4E11-9C10-000000000007"
TEXT = "4B1C0A11-4480-4E11-9C10-000000000008"
COMBINE = "4B1C0A11-4480-4E11-9C10-000000000009"
CHECK_SSH = "4B1C0A11-4480-4E11-9C10-00000000000A"
DND_SSH = "4B1C0A11-4480-4E11-9C10-00000000000B"
DND_GROUP = "4B1C0A11-4480-4E11-9C10-00000000000C"

MARKER = "\ufffc"


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


def _variable(name: str) -> dict:
    return {
        "Value": {"VariableName": name, "Type": "Variable"},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def _text(body: str, attachments: dict) -> dict:
    return {
        "Value": {"string": body, "attachmentsByRange": attachments},
        "WFSerializationType": "WFTextTokenString",
    }


def _slot(body: str, uuid: str, name: str) -> dict:
    """A text token whose only character is one action output."""
    if body != MARKER:
        raise ValueError("slot text must be the object-replacement character")
    return _text(body, {"{0, 1}": {"OutputUUID": uuid, "Type": "ActionOutput", "OutputName": name}})


def check_ssh_script() -> dict:
    """Remote command. The combined sample text is inserted before the heredoc end."""
    prefix = SCRIPT + " check <<'EARLY_BEDTIME_END'\n"
    suffix = "\nEARLY_BEDTIME_END\n"
    body = prefix + MARKER + suffix
    index = body.index(MARKER)
    return _text(
        body,
        {
            f"{{{index}, 1}}": {
                "OutputUUID": COMBINE,
                "Type": "ActionOutput",
                "OutputName": "Combined Text",
            }
        },
    )


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
                    "Values": {"Number": 2, "Unit": 16384},
                },
            ],
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }


def _detail(uuid: str, prop: str) -> dict:
    return _action(
        "is.workflow.actions.properties.health.quantity",
        UUID=uuid,
        WFContentItemPropertyName=prop,
        WFInput=_variable("Repeat Item"),
    )


def _format_date(uuid: str, source: str, source_name: str) -> dict:
    return _action(
        "is.workflow.actions.format.date",
        UUID=uuid,
        WFDateFormatStyle="ISO 8601",
        WFDate=_slot(MARKER, source, source_name),
    )


def check_workflow() -> dict:
    """Shortcut run by a 12:00pm personal automation."""
    sample_line = MARKER + "\t" + MARKER + "\t" + MARKER
    actions = [
        _action(
            "is.workflow.actions.comment",
            WFCommentActionText=(
                "Automation: every day at 12:00pm, run immediately. "
                "Allow Shortcuts to read Sleep in the Health app."
            ),
        ),
        _action(
            "is.workflow.actions.filter.health.quantity",
            UUID=FIND,
            WFContentItemFilter=_health_filter(),
        ),
        _action(
            "is.workflow.actions.repeat.each",
            GroupingIdentifier=REPEAT_GROUP,
            WFControlFlowMode=0,
            WFInput=_output(FIND, "Health Samples"),
        ),
        _detail(DETAIL_VALUE, "Value"),
        _detail(DETAIL_START, "Start Date"),
        _detail(DETAIL_END, "End Date"),
        _format_date(FORMAT_START, DETAIL_START, "Start Date"),
        _format_date(FORMAT_END, DETAIL_END, "End Date"),
        _action(
            "is.workflow.actions.gettext",
            UUID=TEXT,
            WFTextActionText=_text(
                sample_line,
                {
                    "{0, 1}": {
                        "OutputUUID": DETAIL_VALUE,
                        "Type": "ActionOutput",
                        "OutputName": "Value",
                    },
                    "{2, 1}": {
                        "OutputUUID": FORMAT_START,
                        "Type": "ActionOutput",
                        "OutputName": "Formatted Date",
                    },
                    "{4, 1}": {
                        "OutputUUID": FORMAT_END,
                        "Type": "ActionOutput",
                        "OutputName": "Formatted Date",
                    },
                },
            ),
        ),
        _action(
            "is.workflow.actions.appendvariable",
            WFVariableName="Samples",
            WFInput=_output(TEXT, "Text"),
        ),
        _action(
            "is.workflow.actions.repeat.each",
            GroupingIdentifier=REPEAT_GROUP,
            WFControlFlowMode=2,
        ),
        _action(
            "is.workflow.actions.text.combine",
            UUID=COMBINE,
            WFTextSeparator="Custom",
            WFTextCustomSeparator="\n",
            text=_variable("Samples"),
        ),
        _ssh(CHECK_SSH, check_ssh_script()),
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
    """Write both shortcut plists. Returns the check path and the DND path."""
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


if __name__ == "__main__":
    check_path, dnd_path = write_shortcuts()
    print(check_path)
    print(dnd_path)
