-- For existing databases. An index also protects concurrent registrations.
-- If legacy records differ only by email case, resolve those duplicates first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (lower(email));
