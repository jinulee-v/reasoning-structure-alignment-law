from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from prolog_to_catala.sara_fresh.export_catala_tests import FIXTURES,ROOT,load_cases
from prolog_to_catala.sara_fresh.literals import parse_literal,render_literal
from prolog_to_catala.sara_fresh.normalization import InputConflict,normalize_world,to_list_world
from prolog_to_catala.sara_fresh.schema import WORLD_LIST_TYPES,NO_FACTS
from prolog_to_catala.sara_fresh.adapter import catala_inputs
from rsa_formalizer.stages.utils import toolchain_environment
from rsa_formalizer.stages.validation.verification import _json_report

FIXTURE=json.loads(FIXTURES.read_text())
def entity(n):return {'id':n,'kind':'Atom'}
def empty_world():
    result={}
    for family,count in [('dependency',6),('financial',6),('relationship',8),('employment',4),('status',3)]:
        for i in range(1,count+1):result[f'{family}_{i}']=entity(0) if family=='dependency' else deepcopy(FIXTURE['defaults'][family])
    return result

def row(family,kind,identity,**fields):
    result=deepcopy(FIXTURE['defaults'][family]);result.update(kind=kind,identifier=entity(identity),**fields);return result

def income(identity=10,amount='100'):
    return row('financial','Income',identity,agent=entity(1),amount=amount,start='2020-01-01',start_present=True)
def payment(identity=10,amount='100'):
    return row('financial','Payment',identity,patient=entity(1),agent=entity(2),amount=amount,start='2020-01-01',start_present=True)
def birth(identity,when):
    return row('relationship','Birth',identity,subject_1=entity(1),start=when,start_present=True)

class NormalizationTest(unittest.TestCase):
    def test_native_world_migration_is_idempotent_and_preserves_all_gt_facts(self):
        maxima={field:0 for field in WORLD_LIST_TYPES}
        for name,case,_ in load_cases():
            world=case['world']
            with self.subTest(case=name):
                self.assertEqual(set(world),set(WORLD_LIST_TYPES))
                self.assertEqual(to_list_world(world),world)
                inputs={field:case[field] for field in ('world','taxpayer','period')}
                self.assertEqual(catala_inputs(inputs)['world'],world)
                for field,values in world.items():
                    self.assertIsInstance(values,list)
                    maxima[field]=max(maxima[field],len(values))
                    if field!='dependency_candidates':
                        self.assertTrue(all(value['kind'] not in NO_FACTS for value in values))
        self.assertEqual(list(maxima.values()),[6,6,8,4,3])

    def test_list_input_has_no_previous_fixed_capacity(self):
        world=to_list_world(empty_world())
        world['financial_facts']=[income(identity=10+i) for i in range(9)]
        normalized=normalize_world(world)
        self.assertEqual(len(normalized['world']['financial_facts']),9)
        self.assertEqual(len(normalized['transactions']),9)
        self.assertEqual(parse_literal(render_literal('World',world)),world)

    def test_native_and_legacy_inputs_have_the_same_canonical_meaning(self):
        legacy=empty_world();legacy['financial_1']=income()
        self.assertEqual(normalize_world(legacy),normalize_world(to_list_world(legacy)))

    def test_mixed_incomplete_and_nonlist_worlds_are_rejected(self):
        native=to_list_world(empty_world())
        mixed=dict(native,financial_1=income())
        incomplete=dict(native);del incomplete['status_facts']
        nonlist=dict(native,financial_facts={})
        for world in [mixed,incomplete,nonlist,{}]:
            with self.subTest(world=world),self.assertRaises(InputConflict):
                to_list_world(world)

    def test_all_original_cases_and_literal_roundtrips(self):
        cases=list(load_cases());self.assertEqual(len(cases),97)
        for name,case,_ in cases:
            with self.subTest(case=name):self.assertEqual(parse_literal(render_literal('World',case['world'])),case['world'])
    def test_adoption_date_is_not_a_conflicting_birth_date(self):
        records={name:canon for name,_,canon in load_cases()}
        bob=next(x for x in records['TestTaxCase37']['birth_dates'] if x['date']=='2014-01-31')
        self.assertIn('2018-03-04',bob['relationship_starts'])
    def test_conflicting_explicit_birth_dates_rejected(self):
        world=empty_world();world['relationship_1']=birth(10,'2000-01-01');world['relationship_2']=birth(11,'2001-01-01')
        with self.assertRaises(InputConflict):normalize_world(world)
    def test_exact_repeated_row_collapses_without_changing_multiplicity(self):
        world=empty_world();world['financial_1']=income();world['financial_1']['multiplicity']=6;world['financial_2']=deepcopy(world['financial_1'])
        canonical=normalize_world(world)
        self.assertEqual(canonical['duplicate_slots_removed'],['financial_facts[1]']);self.assertEqual(canonical['transactions'][0]['multiplicity'],6)
    def test_same_event_id_with_conflicting_amount_rejected(self):
        world=empty_world();world['financial_1']=income();world['financial_2']=income(amount='101')
        with self.assertRaises(InputConflict):normalize_world(world)
    def test_transaction_aliases_merge_but_equal_independent_payments_do_not(self):
        world=empty_world();world['financial_1']=income();world['financial_2']=payment();world['financial_3']=payment(11)
        canonical=normalize_world(world);self.assertEqual(len(canonical['transactions']),2)
        self.assertEqual(canonical['transactions'][0]['evidence_kinds'],['Income','Payment'])
    def test_transaction_alias_recipient_conflict_rejected(self):
        world=empty_world();world['financial_1']=income();world['financial_2']=payment();world['financial_2']['patient']=entity(3)
        with self.assertRaises(InputConflict):normalize_world(world)
    def test_inverse_parent_and_symmetric_sibling_aliases_merge(self):
        world=empty_world()
        world['relationship_1']=row('relationship','Son',10,subject_1=entity(1),relative_1=entity(2))
        world['relationship_2']=row('relationship','Father',11,subject_1=entity(2),relative_1=entity(1))
        world['relationship_3']=row('relationship','Brother',12,subject_1=entity(1),relative_1=entity(3))
        world['relationship_4']=row('relationship','Sibling',13,subject_1=entity(3),relative_1=entity(1))
        canonical=normalize_world(world);self.assertEqual(len(canonical['parent_edges']),1);self.assertEqual(len(canonical['sibling_edges']),1)
    def test_classification_aliases_form_one_set(self):
        world=empty_world();world['employment_1']=row('employment','Service',10,purpose_1={'Known':'Government'},location_1={'Known':'Government'})
        self.assertEqual(normalize_world(world)['services'][0]['classifications'],['Government'])
    def test_nonresident_alien_is_not_a_no_fact_constructor(self):
        world=empty_world();world['status_1']=row('status','NonresidentAlien',10,subject=entity(1))
        self.assertEqual(normalize_world(world)['world']['status_facts'][0]['kind'],'NonresidentAlien')

class NativeNormalizationTest(unittest.TestCase):
    def test_fact_value_uses_the_same_name_in_schema_and_compiled_replay(self):
        from rsa_formalizer.bobcat import compiled_json
        from rsa_formalizer.stages.utils import extract_input_formats

        with tempfile.TemporaryDirectory(prefix='sara-fact-value-') as tmp:
            project=Path(tmp)
            shutil.copy2(ROOT/'data/raw/sara/Definitions.catala_en',project/'Definitions.catala_en')
            shutil.copy2(ROOT/'data/raw/sara/clerk.toml',project/'clerk.toml')
            (project/'Probe.catala_en').write_text('''> Module Probe
> Using Definitions as W
```catala-metadata
declaration scope Probe:
  input value content W.FactValue
  output present content boolean
```
```catala
scope Probe:
  definition present equals match value with pattern
    -- W.FactValue.Known content known: known != W.KnownValue.OtherKnownValue
    -- W.FactValue.Named content named: named.id != 0
```
''')
            env=toolchain_environment({});env['OPAMROOT']=str(ROOT/'.toolchain/opam')
            formats=extract_input_formats(project,environment=env,timeout=60)
            errors=compiled_json.build_bridges(project,formats,environment=env,timeout=120)
            self.assertEqual(errors,{})
            generated=(project/'_build/ocaml/Definitions.ml').read_text()
            self.assertIn('module FactValue = struct',generated)
            executable=compiled_json.compiled_path(project,'Probe.catala_en','Probe')
            for value,present in [({'Known':'Cash'},True),({'Named':entity(1)},True),({'Known':'OtherKnownValue'},False),({'Named':entity(0)},False)]:
                with self.subTest(value=value):
                    result=subprocess.run([str(executable),'Probe','--trace'],input=json.dumps({'value':value})+'\n',cwd=project,env=env,capture_output=True,text=True,timeout=30,check=True)
                    observed=json.loads(result.stdout)
                    self.assertNotIn('__bridge_error__',observed)
                    self.assertEqual(observed['result']['present'],present,observed)

    def test_raw_api_enforces_consistency_without_extra_repair_scopes(self):
        with tempfile.TemporaryDirectory(prefix='sara-raw-api-') as tmp:
            project=Path(tmp)
            for source in (ROOT/'data/catala_gold/sara').glob('*.catala_en'):
                shutil.copy2(source,project/source.name)
            shutil.copy2(ROOT/'data/raw/sara/Definitions.catala_en',project/'Definitions.catala_en')
            api=(ROOT/'data/raw/sara/Api.catala_en').read_text()
            api+='\n```catala\nscope TotalTax:\n  definition total_tax equals $0\n```\n'
            (project/'Api.catala_en').write_text(api)
            shutil.copy2(ROOT/'data/raw/sara/clerk.toml',project/'clerk.toml')
            world=empty_world();world['financial_1']=income();world['financial_2']=income(amount='101')
            text=['> Module RawGuards','> Using Api as A','> Using Definitions as W','```catala-metadata']
            for name in ['Valid','Conflicting']:
                text+=['#[test]',f'declaration scope {name}:','  result scope A.TotalTax']
            text+=['```','```catala']
            period={'tax_year':2020,'first_day':'2020-01-01','last_day':'2020-12-31'}
            for name,case in [('Valid',empty_world()),('Conflicting',world)]:
                text += [f'scope {name}:','  definition result.world equals '+render_literal('World',to_list_world(case)),'  definition result.taxpayer equals '+render_literal('Entity',entity(1)),'  definition result.period equals '+render_literal('TaxPeriod',period),'  assertion result.total_tax = $0']
            text+=['```'];(project/'RawGuards.catala_en').write_text('\n'.join(text)+'\n')
            env=toolchain_environment({});env['OPAMROOT']=str(ROOT/'.toolchain/opam')
            result=subprocess.run(['clerk','test','RawGuards.catala_en','--json','--color=never'],cwd=project,env=env,capture_output=True,text=True,timeout=180)
            report=_json_report(result.stdout)
            rows={r['scope_name']:r['success'] for f in (report or {}).get('test-results',[]) for r in f['tests']['scopes']}
            self.assertEqual(rows,{'Valid':True,'Conflicting':False},(result.stdout+result.stderr)[-5000:])
            self.assertNotIn('declaration scope', (project/'Definitions.catala_en').read_text())

    def test_native_aliases_and_conflict_guards(self):
        probes=[]
        def probe(name,world,condition='true',valid=True):probes.append((name,world,condition,valid))
        world=empty_world();world['financial_1']=income();world['financial_2']=payment()
        probe('SameTransaction',world,'W.gross_income_individual of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, period = $100')
        other=deepcopy(world);other['financial_2']['identifier']=entity(11)
        probe('DistinctTransactions',other,'W.gross_income_individual of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, period = $200')
        bad=deepcopy(world);bad['financial_2']['amount']='101';probe('ConflictingTransaction',bad,valid=False)
        duplicate=deepcopy(world);duplicate['financial_2']=deepcopy(duplicate['financial_1']);probe('RepeatedIncome',duplicate,'W.gross_income_individual of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, period = $100')
        bad=deepcopy(duplicate);bad['financial_2']['amount']='101';probe('ConflictingRepeatedIncome',bad,valid=False)
        adopt=empty_world();adopt['relationship_1']=birth(10,'2014-01-31');adopt['relationship_2']=row('relationship','Son',11,subject_1=entity(1),relative_1=entity(2),start='2018-03-04',start_present=True)
        probe('AdoptionDate',adopt,'(match (W.date_of_birth of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, true) with pattern -- Absent: false -- Present content born: born = |2014-01-31|)')
        bad=deepcopy(adopt);bad['relationship_2']=birth(11,'2018-03-04');probe('ConflictingBirth',bad,valid=False)
        inverse=empty_world();inverse['relationship_1']=row('relationship','Son',10,subject_1=entity(1),relative_1=entity(2));inverse['relationship_2']=row('relationship','Father',11,subject_1=entity(2),relative_1=entity(1))
        probe('InverseParent',inverse,'number of (W.parent_links of validation.checked_world) = 1')
        inverse['relationship_3']=row('relationship','Brother',12,subject_1=entity(1),relative_1=entity(3));inverse['relationship_4']=row('relationship','Sibling',13,subject_1=entity(3),relative_1=entity(1))
        probe('SymmetricSibling',inverse,'number of (W.sibling_links of validation.checked_world) = 1')
        elected=empty_world();elected['status_1']=row('status','ItemizeDeductions',500,subject=entity(1))
        probe('ExplicitElectionSubject',elected,'W.has_itemization_evidence of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, period')
        deduction=empty_world();deduction['financial_1']=row('financial','Deduction',10,agent=entity(1),amount='0',start='2020-01-01',start_present=True)
        probe('ZeroDeductionEvidence',deduction,'W.has_itemization_evidence of validation.checked_world, W.Entity { -- id: 1 -- kind: W.TermKind.Atom }, period')
        with tempfile.TemporaryDirectory(prefix='sara-normalization-tests-') as tmp:
            p=Path(tmp);shutil.copy2(ROOT/'data/catala_gold/sara/Definitions.catala_en',p/'Definitions.catala_en');shutil.copy2(ROOT/'data/raw/sara/clerk.toml',p/'clerk.toml')
            text=['> Module CanonicalTests','> Using Definitions as W','```catala-metadata']
            for name,_,_,_ in probes:text += ['#[test]',f'declaration scope {name}:','  internal world content W.World','  internal period content W.TaxPeriod','  validation scope W.ValidatedWorld','  output valid content boolean']
            text+=['```','```catala']
            period={'tax_year':2020,'first_day':'2020-01-01','last_day':'2020-12-31'}
            for name,world,condition,_ in probes:
                text += [f'scope {name}:','  definition world equals '+render_literal('World',to_list_world(world)),'  definition period equals '+render_literal('TaxPeriod',period),'  definition validation.world equals world','  definition valid equals validation.checked_world = world','  assertion '+condition]
            text+=['```'];(p/'CanonicalTests.catala_en').write_text('\n'.join(text)+'\n')
            env=toolchain_environment({});env['OPAMROOT']=str(ROOT/'.toolchain/opam')
            result=subprocess.run(['clerk','test','CanonicalTests.catala_en','--json','--color=never'],cwd=p,env=env,capture_output=True,text=True,timeout=180)
            report=_json_report(result.stdout);rows={r['scope_name']:r for f in (report or {}).get('test-results',[]) for r in f['tests']['scopes']}
            self.assertEqual(len(rows),len(probes),(result.stdout+result.stderr)[-5000:])
            for name,_,_,valid in probes:
                with self.subTest(probe=name):
                    self.assertEqual(rows[name]['success'],valid,rows[name])
                    if not valid:self.assertTrue(any('assertion' in e['message'].lower() for e in rows[name]['errors']),rows[name])
if __name__=='__main__':unittest.main()
