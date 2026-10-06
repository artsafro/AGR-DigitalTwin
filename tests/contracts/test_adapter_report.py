import pytest
from pydantic import ValidationError
from dt_ai.core.adapter_report import AdapterReport, Check


def report(**overrides):
    return AdapterReport(**dict(dict(operation="connect", tool_version="prototype",
                                    scope="fixture only", execution="completed",
                                    input_manifest="fixture.json"), **overrides))


@pytest.mark.parametrize('status', ['fail', 'not_run', 'review'])
def test_incomplete_checks_cannot_pass(status):
    r = report(checks=(Check(id='topology', status=status, evidence='qa.json'),))
    assert not r.summary()['required_checks_passed']


def test_empty_report_and_pending_decisions_cannot_pass():
    assert not report().summary()['required_checks_passed']
    check = Check(id='length', status='pass', evidence='qa.json')
    assert report(checks=(check,)).summary()['required_checks_passed']
    assert not report(checks=(check,), pending_decisions=('visual review',)).summary()['required_checks_passed']
    assert not report(checks=(check,), execution='failed').summary()['required_checks_passed']


def test_roundtrip_bounded_summary_and_no_delivery_claim():
    r = report(checks=tuple(Check(id=f'check-{i}', status='fail', evidence='qa.json') for i in range(30)))
    restored = AdapterReport.model_validate_json(r.model_dump_json())
    assert restored == r
    assert restored.summary()['issues_total'] == 30
    assert len(restored.summary()['issues']) == 5
    with pytest.raises(ValidationError):
        report(delivery_passed=True)

