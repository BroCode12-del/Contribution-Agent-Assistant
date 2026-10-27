import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {HMEM} from './meterless-hmem/reference/src/index.ts';

const root = path.dirname(fileURLToPath(import.meta.url));
const raw = fs.readFileSync(0, 'utf8');
if (raw.length > 4096) throw new Error('Input too large');
const input = JSON.parse(raw);
if (!/^[a-f0-9]{32}$/.test(input.flow_id)) throw new Error('Invalid flow');
const hmem = new HMEM({persistDir:process.env.LEARNING_MEMORY_ROOT || path.join(root,'.hmem','learning'),actor:'contribution-learning'});
if (process.argv[2] === 'remember') {
  if (!/^[a-f0-9]{32}$/.test(input.attempt_id) || !['unverified','self_reported_independent','ai_assisted','ai_written_reference'].includes(input.origin) || typeof input.all_passed !== 'boolean') throw new Error('Invalid attempt');
  const source = `flow:${input.flow_id}:attempt:${input.attempt_id}`;
  if (!hmem.store.all().some(row=>row.source===source)) hmem.add({
    content:`Flow ${input.flow_id}. Practice origin=${input.origin}; output_passed=${input.all_passed}. Independent ability is not verified.`,
    source,type:'factual',layer:'working',tags:['csv','practice',input.flow_id,input.origin],confidence:0.95,
    provenance:{origin:'file_save',learnedAt:Date.now(),label:'Recorded assistance declaration and fixed-input output checks',refs:[`learning_flows/${input.flow_id}/flow.json`]}
  });
}
const recalled = hmem.query(`Flow ${input.flow_id} practice origin AI assistance`);
const memories = recalled.memories.filter(row=>row.memory.tags.includes(input.flow_id)).map(row=>({
  id:row.memory.id,origin:row.memory.tags.find(tag=>['unverified','self_reported_independent','ai_assisted','ai_written_reference'].includes(tag)),
  source:row.memory.source,content:row.memory.content,relevance:row.relevance
}));
console.log(JSON.stringify({memories,trace:recalled.trace}));
