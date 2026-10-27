-- Read-only demonstration of the original O1 sample, not new discovery data.
-- Expected saved sample: E1, E2 and E3 paired with O1; availability is held.
SELECT
    o.opportunity_id,
    o.summary,
    o.url,
    o.topic,
    o.availability,
    o.availability_reason,
    o.checked_on,
    ev.e.id AS evidence_id,
    ev.e.code AS code,
    ev.e.file AS file_path,
    ev.e.line AS start_line,
    ev.e.line_end AS end_line,
    ev.e.verification AS verification
FROM (
    SELECT explode(evidence) AS e
    FROM CONTRIBUTION_DEMO.evidence_report
) ev
JOIN CONTRIBUTION_DEMO.opportunity_record o
    ON o.topic = 'pandas.read_csv'
WHERE ev.e.observation = 'Calls pandas.read_csv to load CSV data'
ORDER BY evidence_id;
