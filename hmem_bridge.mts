import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { HMEM } from "./meterless-hmem/reference/src/index.ts";

const projectFolder = path.dirname(fileURLToPath(import.meta.url));

const memory = new HMEM({
  persistDir: path.join(projectFolder, ".hmem"),
  actor: "contribution-agent",
});

const action = process.argv[2];

if (action === "remember") {
  const feedback = JSON.parse(
    fs.readFileSync(
      path.join(projectFolder, "practice_feedback.json"),
      "utf8",
    ),
  );

  const results = feedback.observed_results;
  const source = `practice_feedback.json#${results.submission_sha256}`;

  const content =
    `Python practice ${feedback.practice_id}: ` +
    `submission_origin=${results.submission_origin}; ` +
    `all_passed=${results.all_passed}. ` +
    "These results do not establish independent learner ability.";

  const existing = memory.store.all().find(
    (record) => record.source === source && record.content === content,
  );

  const record = existing ?? memory.add({
    content,
    source,
    confidence: 0.95,
    type: "factual",
    layer: "working",
    tags: ["python", "practice", "assistance"],
    provenance: {
      origin: "file_save",
      learnedAt: Date.now(),
      label: "Captured from recorded practice feedback",
      refs: ["practice_feedback.json"],
    },
  });

  console.log(JSON.stringify(record, null, 2));
} else if (action === "recall") {
  const recalled = memory.query("Python practice P1 submission_origin");
  console.log(JSON.stringify(recalled, null, 2));
} else {
  throw new Error("Choose remember or recall.");
}