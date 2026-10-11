from xml.etree import ElementTree as ET

from spike.grader import EXPECTED, parse_grade


def report(tmp_path, *, omit=None, skip=None, fail=None):
    suite = ET.Element("testsuite")
    for name in EXPECTED:
        if name == omit:
            continue
        test = ET.SubElement(suite, "testcase", name=name)
        if name == skip:
            ET.SubElement(test, "skipped")
        if name == fail:
            ET.SubElement(test, "failure")
    p = tmp_path / "junit.xml"
    ET.ElementTree(suite).write(p)
    return p


def test_missing_or_skipped_oracle_is_invalid(tmp_path):
    name = next(iter(EXPECTED))
    assert parse_grade(report(tmp_path, omit=name), 0)["outcome"] == "INVALID"
    assert parse_grade(report(tmp_path, skip=name), 0)["outcome"] == "INVALID"


def test_critical_failure_cannot_hide_in_points(tmp_path):
    p = report(tmp_path, fail="test_critical_cross_project_key_refused")
    grade = parse_grade(p, 1)
    assert grade["total_score"] == 5
    assert grade["outcome"] == "TASK_FAIL" and grade["critical_passed"] is False


def test_grader_control(tmp_path):
    assert parse_grade(report(tmp_path), 0)["outcome"] == "OK"
