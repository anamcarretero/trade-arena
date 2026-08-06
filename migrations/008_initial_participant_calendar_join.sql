BEGIN;

UPDATE competition_participants AS participant
   SET joined_at = competition.starts_at
  FROM competitions AS competition
 WHERE participant.competition_id = competition.id
   AND participant.joined_late = false
   AND participant.joined_at IS DISTINCT FROM competition.starts_at;

INSERT INTO schema_migrations(version)
VALUES ('008_initial_participant_calendar_join')
ON CONFLICT DO NOTHING;

COMMIT;
