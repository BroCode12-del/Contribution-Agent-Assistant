"""Connected learning tests in isolated folders; no services or real attempts."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import learning_flow as learning
from opportunity_pipeline import fingerprint, now


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rid, self.did, self.run = "a"*32, "b"*32, "c"*32
        self.cid = "owner/importer#1"
        self.evidence = {"review_id":self.rid,"repository":"owner/repo","commit_sha":"d"*40,
                         "evidence":[{"id":"E1","file":"code.py","line":1,"line_end":1,"code":"pd.read_csv('x.csv')","observation":"Calls pandas.read_csv to load CSV data","verification":"static_code_only"}]}
        self.candidate = {"candidate_id":self.cid,"title":"Import CSV","body":"Add CSV import tests.","url":"https://github.com/owner/importer/issues/1","availability":"needs_review","blockers":[]}
        self.assessment = {"candidate_id":self.cid,"requirements":[{"statement":"Add import tests","source_quote":"Add CSV import tests."}],"fit":[],"gaps":["Mapping not established."],"review_notes":["Review required."]}
        self.folder = self.root/'discoveries'/self.did/'runs'/self.rid/self.run
        (self.folder/'assessments').mkdir(parents=True)
        self.status = {"review_id":self.rid,"evidence_sha256":fingerprint(self.evidence),"checked_at":now(),"candidates":[self.candidate]}
        self.save_status()
        import hashlib
        path = self.folder/'assessments'/(hashlib.sha256(self.cid.encode()).hexdigest()+'.json')
        path.write_text(json.dumps({"status":"assessed","assessment":self.assessment}))
        self.patches = [patch.object(learning,'PROJECT',self.root),patch('run_opportunities.load_review',return_value=self.evidence),
                        patch.object(learning,'query_zetaris',return_value={"status":"queried","records":[],"note":"fixture"}),
                        patch.object(learning,'memory',side_effect=lambda flow,attempt=None:{"status":"recalled","memories":[{"id":"fixture-"+a['attempt_id'],"origin":a['submission_origin']} for a in flow['attempts']]})]
        for item in self.patches:
            item.start();self.addCleanup(item.stop)

    def save_status(self):
        (self.folder/'status_checks.json').write_text(json.dumps(self.status))

    def create(self):
        return learning.create_flow(self.rid,self.did,self.run,self.cid)

    def test_binding_and_duplicate_start_preserve_existing_budget(self):
        first=self.create();learning.submit(first['flow_id'],example='incorrect_reference')
        same=self.create()
        self.assertEqual(first['flow_id'],same['flow_id'])
        self.assertEqual(len(same['attempts']),1)
        self.assertEqual(same['candidate_id'],self.cid)
        self.assertEqual(same['evidence_sha256'],fingerprint(self.evidence))

    def test_held_candidate_cannot_start_flow(self):
        self.candidate.update(availability='hold',blockers=['already_assigned']);self.save_status()
        with self.assertRaisesRegex(ValueError,'unblocked'):self.create()

    def test_grade_differentiates_lost_identifiers_and_numeric_strings(self):
        task=learning.task('e'*32,1);correct=learning.expected_records(task)
        self.assertTrue(learning.evaluate(task,correct)['all_passed'])
        wrong=[{**r,'external_id':int(r['external_id'])} for r in correct]
        result=learning.evaluate(task,wrong)
        self.assertFalse(result['all_passed']);self.assertFalse(result['checks'][2]['passed'])
        strings=[{**r,'rating':str(r['rating'])} for r in correct]
        self.assertFalse(learning.evaluate(task,strings)['checks'][3]['passed'])

    def test_failed_output_revises_recommendation(self):
        flow=self.create();result=learning.submit(flow['flow_id'],example='incorrect_reference')
        self.assertEqual(result['recommendation']['next_action'],'revise_import_result')
        self.assertFalse(result['attempts'][0]['results']['independent_ability_established'])

    def test_assisted_pass_recalls_history_and_creates_bound_followup(self):
        flow=self.create();result=learning.submit(flow['flow_id'],example='correct_reference')
        self.assertEqual(result['active_task']['sequence'],2)
        self.assertEqual(result['recommendation']['next_action'],'request_independent_evidence')
        self.assertEqual(result['without_memory_recommendation']['next_action'],'review_measured_practice')
        self.assertTrue(result['recommendation']['memory_ids'])
        self.assertEqual(result['candidate_id'],self.cid)
        self.assertEqual(result['max_attempts'],3)

    def test_identical_submission_cannot_erase_assistance(self):
        flow=self.create();first=learning.submit(flow['flow_id'],example='incorrect_reference')
        result=learning.submit(flow['flow_id'],answer=first['attempts'][0]['answer'],origin='self_reported_independent')
        self.assertEqual(len(result['attempts']),1)
        self.assertEqual(result['attempts'][0]['submission_origin'],'ai_written_reference')

    def test_cap_is_preserved_and_fourth_attempt_changes_nothing(self):
        flow=self.create();fid=flow['flow_id']
        learning.submit(fid,example='incorrect_reference');learning.submit(fid,example='correct_reference')
        third=learning.submit(fid,example='correct_reference')
        self.assertEqual(third['recommendation']['next_action'],'stop_for_user_review')
        before=learning.flow_file(fid).read_bytes()
        with self.assertRaisesRegex(ValueError,'three-attempt'):learning.submit(fid,example='incorrect_reference')
        self.assertEqual(before,learning.flow_file(fid).read_bytes())

    def test_self_report_never_establishes_independent_ability(self):
        flow=self.create();result=learning.submit(flow['flow_id'],learning.expected_records(flow['active_task']),'self_reported_independent')
        self.assertFalse(result['attempts'][0]['results']['independent_ability_established'])
        self.assertEqual(result['recommendation']['opportunity_decision'],'needs_review')

    def test_missing_memory_does_not_promote_passing_output(self):
        flow=self.create()
        with patch.object(learning,'memory',return_value={"status":"unavailable","memories":[]}):
            result=learning.submit(flow['flow_id'],example='correct_reference')
        self.assertEqual(result['recommendation']['next_action'],'review_submission_provenance')

    def test_private_draft_uses_same_issue_and_actual_assistance(self):
        flow=self.create();result=learning.submit(flow['flow_id'],example='correct_reference')
        draft=result['outreach'];self.assertEqual(draft['candidate_id'],self.cid)
        self.assertEqual(draft['review_id'],self.rid);self.assertFalse(draft['sending_allowed'])
        self.assertIn('ai_written_reference',draft['draft']);self.assertIn('4/4',draft['draft'])

    def test_submitted_code_is_data_and_nonfinite_values_are_rejected(self):
        flow=self.create();result=learning.submit(flow['flow_id'],"__import__('os').system('anything')")
        self.assertFalse(result['attempts'][0]['results']['all_passed'])
        with self.assertRaises(ValueError):learning.submit(flow['flow_id'],[{'rating':float('nan')}])

    def test_zetaris_failure_is_not_reported_as_success(self):
        flow=self.create()
        with patch.object(learning,'query_zetaris',side_effect=OSError('fixture')):
            result=learning.sync_flow(flow['flow_id'])
        self.assertEqual(result['zetaris']['status'],'unavailable')


if __name__=='__main__':unittest.main()
