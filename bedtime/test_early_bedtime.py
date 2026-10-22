"""Tests for the early bedtime decision and shortcut plists."""

from __future__ import annotations

import plistlib
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import early_bedtime as bedtime
import shortcuts

PT = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=PT)
TODAY = "2026-10-21"


def at(hour: int, minute: int = 0, day: int = 21) -> datetime:
    """A Pacific timestamp. Hours before 18 on the 20th are the previous day."""
    return datetime(2026, 10, day, hour, minute, tzinfo=PT)


def sample(value: str, start: datetime, end: datetime) -> bedtime.Sample:
    return bedtime.Sample(value, start, end)


class SleepHoursTests(unittest.TestCase):
    def test_stages_sum_and_ignore_a_second_source(self):
        samples = [
            sample("Core", at(23, day=20), at(2)),
            sample("Core", at(23, day=20), at(2)),
            sample("Deep", at(2), at(5)),
            sample("REM", at(5), at(6, 30)),
        ]
        self.assertAlmostEqual(bedtime.sleep_hours(samples, NOW), 7.5)

    def test_under_seven_from_shortcut_lines(self):
        text = (
            "Core\t2026-10-20T23:00:00-07:00\t2026-10-21T02:00:00-07:00\n"
            "Deep\t2026-10-21T02:00:00-07:00\t2026-10-21T05:00:00-07:00\n"
            "In Bed\t2026-10-20T22:30:00-07:00\t2026-10-21T06:00:00-07:00\n"
        )
        hours = bedtime.hours_from_text(text, NOW)
        self.assertAlmostEqual(hours, 6.0)

    def test_in_bed_minus_awake_when_there_are_no_stages(self):
        samples = [
            sample("In Bed", at(22, day=20), at(6)),
            sample("Awake", at(3), at(4)),
        ]
        self.assertAlmostEqual(bedtime.sleep_hours(samples, NOW), 7.0)

    def test_short_in_bed_is_under_seven(self):
        samples = [
            sample("In Bed", at(22, day=20), at(5)),
            sample("Awake", at(3), at(4)),
        ]
        self.assertAlmostEqual(bedtime.sleep_hours(samples, NOW), 6.0)

    def test_afternoon_nap_is_outside_the_window(self):
        samples = [sample("Core", at(14, day=20), at(15, day=20))]
        self.assertIsNone(bedtime.sleep_hours(samples, NOW))

    def test_sample_is_clipped_to_six_pm(self):
        samples = [sample("Core", at(17, day=20), at(20, day=20))]
        self.assertAlmostEqual(bedtime.sleep_hours(samples, NOW), 2.0)

    def test_awake_only_is_zero_hours(self):
        samples = [sample("Awake", at(23, day=20), at(1))]
        self.assertEqual(bedtime.sleep_hours(samples, NOW), 0.0)

    def test_unknown_value_is_not_a_night(self):
        samples = [sample("Something Else", at(23, day=20), at(5))]
        self.assertIsNone(bedtime.sleep_hours(samples, NOW))

    def test_bad_lines_are_skipped(self):
        text = "nope\nCore\tnot-a-date\t2026-10-21T01:00:00-07:00\n"
        self.assertEqual(bedtime.parse_samples(text, PT), [])


class PlanTests(unittest.TestCase):
    def test_short_night_arms_and_sends_once(self):
        plan = bedtime.plan_check(bedtime.State(), TODAY, 6.25, [])
        self.assertEqual(plan.outcome, "early")
        self.assertTrue(plan.send_remind)
        self.assertEqual(plan.state.early_date, TODAY)
        self.assertEqual(plan.state.reminded, TODAY)
        self.assertEqual(plan.state.sleep_hours, "6.25")

        again = bedtime.plan_check(plan.state, TODAY, 6.25, [])
        self.assertEqual(again.outcome, "early")
        self.assertFalse(again.send_remind)

    def test_seven_hours_does_not_arm(self):
        plan = bedtime.plan_check(bedtime.State(), TODAY, 7.0, [])
        self.assertEqual(plan.outcome, "normal")
        self.assertFalse(plan.send_remind)
        self.assertEqual(plan.state.early_date, "")

    def test_enough_sleep_clears_an_arm_from_earlier_today(self):
        armed = bedtime.State(early_date=TODAY, reminded=TODAY, blocked=TODAY, cherry=TODAY)
        plan = bedtime.plan_check(armed, TODAY, 8.0, [])
        self.assertEqual(plan.outcome, "normal")
        self.assertEqual(plan.state.early_date, "")
        self.assertEqual(plan.state.blocked, "")
        self.assertEqual(plan.state.cherry, "")
        self.assertEqual(plan.state.reminded, TODAY)

    def test_holiday_skips_and_disarms(self):
        armed = bedtime.State(early_date=TODAY, reminded=TODAY)
        plan = bedtime.plan_check(armed, TODAY, 4.0, [TODAY])
        self.assertEqual(plan.outcome, "holiday")
        self.assertFalse(plan.send_remind)
        self.assertEqual(plan.state.early_date, "")

    def test_missing_holiday_list_does_not_arm(self):
        plan = bedtime.plan_check(bedtime.State(), TODAY, 4.0, None)
        self.assertEqual(plan.outcome, "holiday-unknown")
        self.assertFalse(plan.send_remind)
        self.assertEqual(plan.state.early_date, "")

    def test_no_samples_leaves_state_alone(self):
        previous = bedtime.State(early_date="2026-10-20", sleep_hours="5.00")
        plan = bedtime.plan_check(previous, TODAY, None, [])
        self.assertEqual(plan.outcome, "no-data")
        self.assertEqual(plan.state, previous)

    def test_failed_remind_can_retry(self):
        previous = bedtime.State()
        plan = bedtime.plan_check(previous, TODAY, 6.0, [])
        pending = bedtime.state_before_remind(previous, plan)
        self.assertEqual(pending.early_date, TODAY)
        self.assertEqual(pending.reminded, "")
        self.assertEqual(plan.state.reminded, TODAY)

    def test_apply_blocks_and_messages_once(self):
        armed = bedtime.State(early_date=TODAY)
        plan = bedtime.plan_apply(armed, TODAY, [])
        self.assertTrue(plan.block)
        self.assertTrue(plan.cherry)

        calls = []
        state, label = bedtime.run_apply(
            armed, TODAY, [], lambda: calls.append("block"), lambda: calls.append("cherry")
        )
        self.assertEqual(calls, ["block", "cherry"])
        self.assertEqual(label, "applied")
        self.assertEqual(state.blocked, TODAY)
        self.assertEqual(state.cherry, TODAY)

        again = bedtime.plan_apply(state, TODAY, [])
        self.assertFalse(again.block)
        self.assertFalse(again.cherry)

    def test_apply_skips_a_holiday_and_an_unarmed_day(self):
        armed = bedtime.State(early_date=TODAY)
        self.assertEqual(bedtime.plan_apply(armed, TODAY, [TODAY]), bedtime.ApplyPlan(False, False))
        self.assertEqual(
            bedtime.plan_apply(bedtime.State(), TODAY, []),
            bedtime.ApplyPlan(False, False),
        )
        self.assertEqual(bedtime.plan_apply(armed, TODAY, None), bedtime.ApplyPlan(False, False))

    def test_cherry_failure_keeps_the_block_flag(self):
        def fail():
            raise RuntimeError("telegram down")

        state, label = bedtime.run_apply(
            bedtime.State(early_date=TODAY), TODAY, [], lambda: None, fail
        )
        self.assertEqual(label, "cherry-failed")
        self.assertEqual(state.blocked, TODAY)
        self.assertEqual(state.cherry, "")

    def test_status_word(self):
        armed = bedtime.State(early_date=TODAY)
        self.assertEqual(bedtime.status_label(armed, TODAY, []), "early")
        self.assertEqual(bedtime.status_label(armed, TODAY, [TODAY]), "normal")
        self.assertEqual(bedtime.status_label(bedtime.State(), TODAY, []), "normal")
        self.assertEqual(bedtime.status_label(armed, TODAY, None), "normal")

    def test_remind_notes_name_the_threshold(self):
        notes = bedtime.remind_notes(6.24)
        self.assertIn("6.2 hours", notes)
        self.assertIn("8:30pm", notes)
        self.assertIn("10pm", notes)


class ShortcutTests(unittest.TestCase):
    def test_check_shortcut_reads_sleep_and_calls_the_script(self):
        workflow = shortcuts.check_workflow()
        identifiers = [item["WFWorkflowActionIdentifier"] for item in workflow["WFWorkflowActions"]]
        self.assertIn("is.workflow.actions.filter.health.quantity", identifiers)
        self.assertIn("is.workflow.actions.runsshscript", identifiers)
        ssh = workflow["WFWorkflowActions"][-1]["WFWorkflowActionParameters"]
        script = ssh["WFSSHScript"]["Value"]["string"]
        self.assertIn("early_bedtime.py", script)
        self.assertIn(" check ", script)
        self.assertEqual(ssh["WFSSHHost"], "192.168.1.101")
        self.assertEqual(ssh["WFSSHPort"], "62561")
        health = workflow["WFWorkflowActions"][1]["WFWorkflowActionParameters"]
        type_row = health["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"][0]
        self.assertEqual(type_row["Values"]["Enumeration"]["Value"], "Sleep")
        marker = script.index("\ufffc")
        attachment = ssh["WFSSHScript"]["Value"]["attachmentsByRange"][f"{{{marker}, 1}}"]
        self.assertEqual(attachment["OutputUUID"], shortcuts.COMBINE)

    def test_dnd_shortcut_turns_focus_on_only_after_status(self):
        workflow = shortcuts.dnd_workflow()
        identifiers = [item["WFWorkflowActionIdentifier"] for item in workflow["WFWorkflowActions"]]
        self.assertEqual(
            identifiers,
            [
                "is.workflow.actions.comment",
                "is.workflow.actions.runsshscript",
                "is.workflow.actions.conditional",
                "is.workflow.actions.dnd.set",
                "is.workflow.actions.conditional",
                "is.workflow.actions.conditional",
            ],
        )
        ssh = workflow["WFWorkflowActions"][1]["WFWorkflowActionParameters"]["WFSSHScript"]
        self.assertIn("status", ssh)
        condition = workflow["WFWorkflowActions"][2]["WFWorkflowActionParameters"]
        self.assertEqual(condition["WFConditionalActionString"], "early")
        dnd = workflow["WFWorkflowActions"][3]["WFWorkflowActionParameters"]
        self.assertEqual(dnd["Operation"], "Turn")
        self.assertTrue(dnd["Enabled"])

    def test_written_plist_round_trips(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            check_path, dnd_path = shortcuts.write_shortcuts(Path(folder))
            check = plistlib.loads(check_path.read_bytes())
            dnd = plistlib.loads(dnd_path.read_bytes())
        self.assertEqual(check["WFWorkflowName"], "Early Bedtime Check")
        self.assertEqual(dnd["WFWorkflowName"], "Early Bedtime Do Not Disturb")


class HoursArgTests(unittest.TestCase):
    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            bedtime.parse_hours_arg("-1")
        with self.assertRaises(ValueError):
            bedtime.parse_hours_arg("30")
        self.assertEqual(bedtime.parse_hours_arg("6.5"), 6.5)


if __name__ == "__main__":
    unittest.main()
