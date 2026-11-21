"""Offline regression: acknowledgements cannot contradict known sourcing facts."""
import json
import pytest
from sqlalchemy import create_engine
from src.database.models import Base
from src import readiness


@pytest.mark.parametrize('overridden', [[], ['supplier_agreement']])
def test_declared_retail_marketplace_model_cannot_pass_supplier_agreement(tmp_path, monkeypatch, overridden):
    (tmp_path/'config').mkdir()
    (tmp_path/'main.py').write_text('', encoding='utf-8')
    source = tmp_path/'src/automation'
    source.mkdir(parents=True)
    (source/'engine.py').write_text('def guard():\n    validate_source_unit_cost(1)\n', encoding='utf-8')
    decisions = {'supplier_agreement': {'type':'retail_purchase_per_customer_order',
        'wholesale_agreement':False, 'dropship_agreement':False, 'user_acknowledged':True},
        'supervised_trial_override': {'enabled':True, 'overridden_blockers':overridden}}
    (tmp_path/'config/operator_decisions.json').write_text(json.dumps(decisions), encoding='utf-8')
    db = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(db)
    monkeypatch.setattr(readiness, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(readiness, 'read_config', lambda: {'SUPPLIER_AGREEMENT_CONFIRMED':'true'})
    monkeypatch.setattr(readiness, 'init_database', lambda: db)
    monkeypatch.setattr(readiness, 'probe_payment_execution', lambda **kw: {'passed':False})
    report = readiness.build_report(live=False)
    check = next(c for c in report['checks'] if c['name']=='supplier_agreement')
    assert check['passed'] is False
    assert 'supplier_agreement' in report['supervised_trial_blockers']
