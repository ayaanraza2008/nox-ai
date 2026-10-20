-- NOX consent-based location sharing schema.
-- Apply with the project's PostgreSQL/Supabase migration workflow before enabling the API.
-- Policies use a transaction-local app.nox_user_id set only after NOX validates its account session.
-- Do not expose this custom GUC as a client-controlled SQL connection.

CREATE TABLE IF NOT EXISTS nox_location_devices (
  id text PRIMARY KEY,
  owner_id text NOT NULL,
  label text NOT NULL,
  platform text NOT NULL CHECK (platform IN ('android','ios')),
  token_hash text NOT NULL UNIQUE,
  sharing_enabled boolean NOT NULL DEFAULT false,
  consent_expires_at timestamptz,
  latitude double precision,
  longitude double precision,
  accuracy_m double precision,
  last_location_at timestamptz,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  CHECK (accuracy_m IS NULL OR accuracy_m BETWEEN 0 AND 10000)
);
CREATE INDEX IF NOT EXISTS idx_nox_location_devices_owner ON nox_location_devices(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_nox_location_devices_seen ON nox_location_devices(last_seen_at);

CREATE TABLE IF NOT EXISTS nox_location_enrollment_codes (
  id text PRIMARY KEY,
  owner_id text NOT NULL,
  code_hash text NOT NULL UNIQUE,
  label text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_nox_location_enrollment_expiry ON nox_location_enrollment_codes(expires_at);

CREATE TABLE IF NOT EXISTS nox_location_invites (
  id text PRIMARY KEY,
  inviter_id text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  status text NOT NULL CHECK (status IN ('pending','accepted','revoked')) DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  accepted_by text,
  accepted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_nox_location_invites_inviter ON nox_location_invites(inviter_id, status);

CREATE TABLE IF NOT EXISTS nox_location_shares (
  id text PRIMARY KEY,
  owner_id text NOT NULL,
  viewer_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('active','revoked')) DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  CONSTRAINT nox_location_shares_owner_viewer_unique UNIQUE(owner_id, viewer_id),
  CHECK (owner_id <> viewer_id)
);
CREATE INDEX IF NOT EXISTS idx_nox_location_shares_viewer ON nox_location_shares(viewer_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_nox_location_shares_owner ON nox_location_shares(owner_id, status, expires_at);

CREATE TABLE IF NOT EXISTS nox_location_history (
  id text PRIMARY KEY,
  device_id text NOT NULL REFERENCES nox_location_devices(id) ON DELETE CASCADE,
  owner_id text NOT NULL,
  latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
  longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
  accuracy_m double precision NOT NULL CHECK (accuracy_m BETWEEN 0 AND 10000),
  captured_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nox_location_history_device_time ON nox_location_history(device_id, captured_at DESC);

ALTER TABLE nox_location_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE nox_location_devices FORCE ROW LEVEL SECURITY;
ALTER TABLE nox_location_enrollment_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nox_location_enrollment_codes FORCE ROW LEVEL SECURITY;
ALTER TABLE nox_location_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE nox_location_invites FORCE ROW LEVEL SECURITY;
ALTER TABLE nox_location_shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE nox_location_shares FORCE ROW LEVEL SECURITY;
ALTER TABLE nox_location_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE nox_location_history FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS nox_location_devices_scope ON nox_location_devices;
CREATE POLICY nox_location_devices_scope ON nox_location_devices
  USING (
    owner_id = current_setting('app.nox_user_id', true)
    OR current_setting('app.nox_ingest', true) = 'true'
    OR EXISTS (
      SELECT 1 FROM nox_location_shares s
      WHERE s.owner_id = nox_location_devices.owner_id
        AND s.viewer_id = current_setting('app.nox_user_id', true)
        AND s.status = 'active' AND s.expires_at > now()
    )
  )
  WITH CHECK (
    owner_id = current_setting('app.nox_user_id', true)
    OR current_setting('app.nox_ingest', true) = 'true'
  );

DROP POLICY IF EXISTS nox_location_enrollment_scope ON nox_location_enrollment_codes;
CREATE POLICY nox_location_enrollment_scope ON nox_location_enrollment_codes
  USING (owner_id = current_setting('app.nox_user_id', true) OR current_setting('app.nox_enroll', true) = 'true')
  WITH CHECK (owner_id = current_setting('app.nox_user_id', true) OR current_setting('app.nox_enroll', true) = 'true');

DROP POLICY IF EXISTS nox_location_invites_scope ON nox_location_invites;
CREATE POLICY nox_location_invites_scope ON nox_location_invites
  USING (inviter_id = current_setting('app.nox_user_id', true) OR current_setting('app.nox_invite_accept', true) = 'true')
  WITH CHECK (inviter_id = current_setting('app.nox_user_id', true) OR current_setting('app.nox_invite_accept', true) = 'true');

DROP POLICY IF EXISTS nox_location_shares_scope ON nox_location_shares;
CREATE POLICY nox_location_shares_scope ON nox_location_shares
  USING (owner_id = current_setting('app.nox_user_id', true) OR viewer_id = current_setting('app.nox_user_id', true))
  WITH CHECK (owner_id = current_setting('app.nox_user_id', true) OR viewer_id = current_setting('app.nox_user_id', true));

DROP POLICY IF EXISTS nox_location_history_scope ON nox_location_history;
CREATE POLICY nox_location_history_scope ON nox_location_history
  USING (
    owner_id = current_setting('app.nox_user_id', true)
    OR EXISTS (
      SELECT 1 FROM nox_location_shares s
      WHERE s.owner_id = nox_location_history.owner_id
        AND s.viewer_id = current_setting('app.nox_user_id', true)
        AND s.status = 'active' AND s.expires_at > now()
    )
  )
  WITH CHECK (owner_id = current_setting('app.nox_user_id', true) OR current_setting('app.nox_ingest', true) = 'true');
