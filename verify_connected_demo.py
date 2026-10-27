"""Explicit live Zetaris/H-MEM integration check; real practice state untouched.

Uses the saved, validated public issue assessment and an isolated learning
folder. No model call, outreach, or submission occurs. Examples are AI-written.
"""
import copy
import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values
import learning_flow as learning
from opportunity_pipeline import now, write_json


def main():
    root = Path(__file__).parent
    review_id = "01cdd3a0db1c4e21b8a850aa5593287d"
    candidate_id = "makingdreamscometrue/pontil#8"
    verification = json.loads((root/'step10_verification.json').read_text())
    discovery_id,run_id = verification['discovery_id'],verification['run_id']
    original_paths = [root/'agent_state.json',root/'practice_feedback.json',*(root/'learning_flows').glob('*/flow.json')]
    originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in original_paths}
    settings = dotenv_values(root/'.env')
    with tempfile.TemporaryDirectory(prefix='connected-flow-') as directory:
        isolated = Path(directory)
        source_folder = root/'discoveries'/discovery_id/'runs'/review_id/run_id
        shutil.copytree(source_folder,isolated/source_folder.relative_to(root))
        with patch.object(learning,'PROJECT',isolated),patch.object(learning,'dotenv_values',return_value=settings):
            flow = learning.create_flow(review_id,discovery_id,run_id,candidate_id)
            flow_id = flow['flow_id']
            joined = learning.sync_flow(flow_id)
            assert joined['zetaris']['status']=='queried'
            assert len(joined['zetaris']['records'])==len(flow['evidence'])
            wrong=learning.submit(flow_id,example='incorrect_reference')
            assert wrong['recommendation']['next_action']=='revise_import_result'
            passed=learning.submit(flow_id,example='correct_reference')
            assert passed['attempts'][-1]['results']['all_passed']
            assert passed['active_task']['sequence']==2
            assert passed['memory']['status']=='recalled' and passed['recommendation']['memory_ids']
            assert passed['without_memory_recommendation']['next_action']!=passed['recommendation']['next_action']
            final=learning.submit(flow_id,example='correct_reference')
            assert len(final['attempts'])==3 and final['recommendation']['next_action']=='stop_for_user_review'
            before=learning.flow_file(flow_id).read_bytes()
            try:learning.submit(flow_id,example='incorrect_reference')
            except ValueError:pass
            else:raise AssertionError('Fourth attempt unexpectedly accepted')
            assert before==learning.flow_file(flow_id).read_bytes()
            assert final['outreach']['candidate_id']==candidate_id and final['outreach']['sending_allowed'] is False
            proof={'verified_at':now(),'status':'passed','execution':'isolated verification using real Zetaris and official H-MEM reference engine',
                   'test_fixture':True,'source_run_id':run_id,'review_id':review_id,'candidate_id':candidate_id,
                   'zetaris_records':len(joined['zetaris']['records']),'zetaris_source_kind':joined['zetaris']['source_kind'],
                   'first_feedback_action':wrong['recommendation']['next_action'],'after_assisted_pass':passed['recommendation']['next_action'],
                   'without_memory':passed['without_memory_recommendation']['next_action'],'memory_ids':passed['recommendation']['memory_ids'],
                   'followup_created':True,'attempts_used':3,'max_attempts':3,'fourth_attempt_rejected':True,'final_action':final['recommendation']['next_action'],
                   'draft_issue_binding_matches':True,'outreach_sent':False,'independent_ability_established':False,
                   'practice_measurement':'Structured output on fixed inputs; no submitted code execution or mastery claim.'}
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==value for path,value in originals.items())
    proof['real_project_state_unchanged']=True
    write_json(root/'connected_demo_verification.json',proof)
    print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
