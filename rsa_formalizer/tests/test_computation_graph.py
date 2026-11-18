"""Domain-neutral checks for partial computation correspondence and fixed oracles."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rsa_formalizer.bobcat import computation_graph as graph
from rsa_formalizer.stages.reasoning_structure_alignment import computation_alignment as stage, provision_testing as reports
from rsa_formalizer.stages import utils as exp


class ComputationGraphTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshot = self.root / 'analysis/snapshot'
        self.snapshot.mkdir(parents=True)
        (self.snapshot / 'Rules.catala_en').write_text('''```catala
declaration scope Compute:
 input subject content Subject
 output eligible content boolean
 output amount content integer
```
<!-- rsa-block-id: rule:b1; role: provision; provision-id: rules/P1; -->
```catala
scope Compute:
 definition eligible equals false
```
<!-- rsa-block-id: rule:b2; role: provision; provision-id: rules/P2; -->
```catala
scope Compute:
 definition amount equals 731
```
''')
        self.tree = [{'kind': 'call', 'name': 'Compute', 'children': [
            {'kind': 'variable', 'name': 'Compute.subject', 'definition_id': 1,
             'io': {'io_input': 'OnlyInput'}, 'value': {'id': 7}, 'reads': []},
            {'kind': 'variable', 'name': 'Compute.eligible', 'definition_id': 2,
             'value': False, 'reads': [{'definition_id': 1}]},
            {'kind': 'variable', 'name': 'Compute.amount', 'definition_id': 3,
             'value': 731, 'reads': [{'definition_id': 2}]}]}]
        self.solution = 'Under P1, eligible is true. Under P2, amount is 42.'
        self.nodes = {'nodes': [
            {'id': 10, 'quantity': 'Compute.eligible', 'label': 'Eligibility', 'value': 'true',
             'provision': 'rules/P1', 'premises': [], 'evidence': 'Under P1, eligible is true.'},
            {'id': 20, 'quantity': 'Compute.amount', 'label': 'Amount', 'value': '42',
             'provision': 'rules/P2', 'premises': [10], 'evidence': 'Under P2, amount is 42.'}]}

    def prepare(self, tree=None):
        return graph.prepare(tree or self.tree, self.snapshot, {'subject': {'id': 7}})

    def test_frontier_provision_and_evidence(self):
        result = graph.compare(self.prepare(), self.nodes, self.solution)
        self.assertEqual(len(result['value_mismatches']), 2)
        self.assertEqual([row['quantity'] for row in result['earliest_comparable_mismatches']], ['Compute.eligible'])
        self.assertEqual(result['value_mismatches'][0]['catala_provisions'], ['rules/P2'])
        first = result['earliest_comparable_mismatches'][0]
        self.assertEqual(first['catala_provisions'], ['rules/P1'])
        self.assertEqual(first['llm_provision'], 'rules/P1')
        self.assertEqual(result['llm_graph']['nodes'][1]['premises'], [0])
        self.assertEqual(first['public_input_contexts'], [{'subject': {'id': 7}}])

    def test_source_only_cache_prefix_and_no_computed_values(self):
        prepared = self.prepare()
        catalog = prepared['catalog']
        prompt, schema = stage.extraction_prompt(catalog, graph.extraction_context(prepared), self.solution, ['rules/P1', 'rules/P2'])
        self.assertNotIn('731', prompt)
        self.assertNotIn('definition amount', prompt)
        other_tree = copy.deepcopy(self.tree)
        other_tree[0]['children'][0]['value'] = {'id': 8}
        other = graph.prepare(other_tree, self.snapshot, {'subject': {'id': 8}})
        second, second_schema = stage.extraction_prompt(other['catalog'], graph.extraction_context(other), self.solution, ['rules/P1', 'rules/P2'])
        self.assertEqual(prompt.prefix, second.prefix)
        self.assertEqual(schema, second_schema)
        self.assertNotEqual(prompt.suffix, second.suffix)

    def test_literal_evidence_backward_edges_and_unique_ids(self):
        catalog = self.prepare()['catalog']
        for change in ('quote', 'later', 'duplicate', 'quantity'):
            nodes = copy.deepcopy(self.nodes)
            if change == 'quote': nodes['nodes'][0]['evidence'] = 'invented computation'
            if change == 'later': nodes['nodes'][0]['premises'] = [20]
            if change == 'duplicate': nodes['nodes'][1]['id'] = 10
            if change == 'quantity': nodes['nodes'][0]['quantity'] = 'Unknown.result'
            with self.subTest(change=change), self.assertRaises(ValueError):
                graph.validate_graph(nodes, catalog, self.solution)

    def test_missing_ambiguous_and_incomparable_are_not_value_mismatches(self):
        tree = copy.deepcopy(self.tree)
        tree.append(copy.deepcopy(tree[0]))
        tree[1]['children'][0].update(definition_id=11, value={'id': 8})
        tree[1]['children'][1].update(definition_id=12, value=True)
        tree[1]['children'][2].update(definition_id=13, value=42)
        result = graph.compare(graph.prepare(tree, self.snapshot, {'subjects': [{'id': 7}, {'id': 8}]}), self.nodes, self.solution)
        self.assertEqual(result['value_mismatches'], [])
        self.assertEqual(len(result['ambiguous']), 2)
        result = graph.compare(self.prepare(), {'nodes': []}, self.solution)
        self.assertEqual(len(result['missing_llm_counterparts']), 2)
        nodes = copy.deepcopy(self.nodes)
        nodes['nodes'][1]['value'] = 'unknown'
        result = graph.compare(self.prepare(), nodes, self.solution)
        self.assertEqual(len(result['incomparable']), 1)

    def test_existing_money_tolerance_and_exact_other_numeric_types(self):
        self.assertTrue(graph._equal('10.00', '10.50', 'money'))
        self.assertFalse(graph._equal('10.00', '11.00', 'money'))
        self.assertFalse(graph._equal(10, '10.50', 'integer'))
        self.assertIsNone(graph._equal(False, '0', 'boolean'))

    def test_repaired_alias_remaps_without_reextracting_oracle(self):
        prepared = self.prepare()
        frozen = copy.deepcopy(prepared['catalog'])
        renamed = copy.deepcopy(prepared)
        renamed['canonical']['Compute.eligible'] = 'Repaired.flag'
        renamed['selected']['Repaired.flag'] = renamed['selected'].pop('Compute.eligible')
        renamed['ancestors']['Repaired.flag'] = set()
        for row in renamed['catalog']:
            if row['quantity'] == 'Compute.eligible': row['quantity'] = 'Repaired.flag'
        result = graph.compare(renamed, self.nodes, self.solution, frozen)
        self.assertIn('Repaired.flag', [row['quantity'] for row in result['value_mismatches']])
        self.assertEqual(self.nodes['nodes'][0]['quantity'], 'Compute.eligible')

    def test_pre_replay_extraction_uses_public_input_without_catala_trace(self):
        config = {'run_id': 'test', 'repair': {'computation_graph_alignment': {
            'enabled': True, 'max_extraction_attempts': 1}},
            'reasoning_trace': {'provider': 'openai', 'model': 'test-model'}}
        case = {'id': 'pre-replay', 'inputs': {'subject': {'id': 7}}}
        response = {'output_text': self.solution}
        sampled = {'output_text': json.dumps(self.nodes), 'request_id': 'r1'}
        with mock.patch.object(stage.reasoning, '_statutes', return_value='[rules/P1] [rules/P2]'), \
             mock.patch.object(stage.reasoning, '_allowed_provision_ids', return_value=['rules/P1', 'rules/P2']), \
             mock.patch.object(stage.reasoning, '_sample', return_value=sampled) as sample, \
             mock.patch.object(stage.usage_tracking, 'api_call', side_effect=lambda r,m,k,fn:fn()):
            result = stage.extract_before_replay(self.root, config, self.snapshot, case, response)
            self.assertEqual(result['status'], 'complete')
            prompt = sample.call_args.args[1]
            self.assertIn('"id": 7', prompt)
            self.assertIn('NO PROGRAM EXECUTION OBSERVED', prompt)
            self.assertNotIn('731', prompt)
            self.assertEqual(stage.extract_before_replay(self.root, config, self.snapshot,
                                                         case, response), result)
            sample.assert_called_once()

    def test_reports_prefer_value_graph_and_keep_error_artifacts(self):
        targets = [{'provision_id': 'rules/P1', 'blocks': [{'block_id': 'rule:b1'}]},
                   {'provision_id': 'rules/P2', 'blocks': [{'block_id': 'rule:b2'}]}]
        results = [{'target': t, 'status': 'accepted', 'accepted_tests': [
            {'case': {'id': str(i)}, 'reasoning': {'output_text': self.solution}}]} for i,t in enumerate(targets)]
        alignment = graph.compare(self.prepare(), self.nodes, self.solution)
        rows = [{'id': '0', 'final_answer_aligned': True, 'computation_graph_alignment': alignment},
                {'id': '1', 'code_execution_error': True, 'code_execution_diagnostic': 'runtime failure'}]
        index = reports.write_reports(self.root, results, {'cases': rows})
        self.assertEqual(index['reports'][0]['linked_provisions'], ['rules/P1', 'rules/P2'])
        self.assertTrue((self.root / 'feedback' / index['diagnostics'][0]['report']).is_file())
        rows = [{'id': '0', 'final_answer_aligned': True,
                 'provision_alignment': {'llm_only': ['P2']},
                 'computation_graph_alignment': {'status': 'compared', 'missing_llm_counterparts': ['quantity']}}]
        self.assertEqual(reports.write_reports(self.root, results, {'cases': rows})['reports'], [])


if __name__ == '__main__':
    unittest.main()
