-- Apply after schemas.sql / 001. Transactional, repeatable migration.
CREATE TABLE IF NOT EXISTS auth_sessions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 refresh_hash TEXT UNIQUE NOT NULL,
 device_name VARCHAR(100) NOT NULL DEFAULT 'Устройство',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '90 days',
 absolute_expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '365 days',
 revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE TABLE IF NOT EXISTS used_refresh_tokens (
 token_hash TEXT PRIMARY KEY,
 session_id UUID NOT NULL REFERENCES auth_sessions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS password_resets (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT UNIQUE NOT NULL,
 issued_by UUID REFERENCES users(id) ON DELETE SET NULL,
 expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 minutes',
 consumed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS auth_rate_limits (
 key TEXT PRIMARY KEY, attempts INTEGER NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS module_members (
 module_id UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
 user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','left')),
 PRIMARY KEY(module_id,user_id)
);
CREATE TABLE IF NOT EXISTS invitations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 module_id UUID REFERENCES modules(id) ON DELETE CASCADE,
 created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT UNIQUE NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('teacher','student')),
 expires_at TIMESTAMPTZ NOT NULL,
 max_uses INTEGER NOT NULL CHECK(max_uses > 0),
 uses INTEGER NOT NULL DEFAULT 0,
 revoked_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS invitation_courses (
 invitation_id UUID NOT NULL REFERENCES invitations(id) ON DELETE CASCADE,
 discipline_id UUID NOT NULL REFERENCES disciplines(id) ON DELETE CASCADE,
 PRIMARY KEY(invitation_id,discipline_id)
);
CREATE TABLE IF NOT EXISTS invitation_acceptances (
 invitation_id UUID NOT NULL REFERENCES invitations(id) ON DELETE CASCADE,
 user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(invitation_id,user_id)
);
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE RESTRICT;
-- Historical authors are unknown: keep NULL; only module creator/admin may delete them.
CREATE TABLE IF NOT EXISTS security_events (
 id BIGSERIAL PRIMARY KEY,
 actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
 action TEXT NOT NULL,
 subject_id UUID,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Make historical creators visible in member lists; creator identity remains authoritative.
INSERT INTO discipline_members(discipline_id,user_id,role,status)
SELECT id,author_id,'owner','active' FROM disciplines
ON CONFLICT(discipline_id,user_id) DO UPDATE SET role='owner',status='active';
