-- 1. ТАБЛИЦА: users (Пользователи и авторизация)
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NULL,
    yandex_id     VARCHAR(255) UNIQUE NULL,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    middle_name   VARCHAR(100) NULL,
    avatar_id     UUID NULL,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NULL
);

-- 2. ТАБЛИЦА: modules (Образовательные модули программы обучения)
CREATE TABLE IF NOT EXISTS modules (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(255) NOT NULL,
    description TEXT NULL,
    curator_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NULL
);

-- 3. ТАБЛИЦА: disciplines (Курсы / дисциплины)
CREATE TABLE IF NOT EXISTS disciplines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id       UUID NULL REFERENCES modules(id) ON DELETE SET NULL,
    author_id       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    title           VARCHAR(255) NOT NULL,
    discipline_type VARCHAR(32) NOT NULL DEFAULT 'module' CHECK (discipline_type IN ('module', 'core', 'elective')),
    status          VARCHAR(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    description     TEXT NULL,
    invite_code     VARCHAR(32) UNIQUE NOT NULL,
    cover_file_id   UUID NULL,
    ends_at         DATE NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NULL
);

-- 4. ТАБЛИЦА: teams (Студенческие команды внутри дисциплины)
CREATE TABLE IF NOT EXISTS teams (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discipline_id UUID NOT NULL REFERENCES disciplines(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,
    description   TEXT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. ТАБЛИЦА: discipline_members (Участники курса: преподаватели, студенты)
CREATE TABLE IF NOT EXISTS discipline_members (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discipline_id UUID NOT NULL REFERENCES disciplines(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role          VARCHAR(32) NOT NULL DEFAULT 'student' CHECK (role IN ('owner', 'teacher', 'student')),
    status        VARCHAR(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'left')),
    team_id       UUID NULL REFERENCES teams(id) ON DELETE SET NULL,
    enrolled_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_discipline_user UNIQUE (discipline_id, user_id)
);

-- 6. ТАБЛИЦА: lessons (Уроки / темы занятий)
CREATE TABLE IF NOT EXISTS lessons (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discipline_id    UUID NOT NULL REFERENCES disciplines(id) ON DELETE CASCADE,
    title            VARCHAR(255) NOT NULL,
    order_index      INTEGER NOT NULL DEFAULT 0,
    content_markdown TEXT NULL,
    is_published     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NULL
);

-- 7. ТАБЛИЦА: assignments (Задания / лабораторные работы)
CREATE TABLE IF NOT EXISTS assignments (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id            UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    title                VARCHAR(255) NOT NULL,
    description_markdown TEXT NOT NULL,
    target_type          VARCHAR(32) NOT NULL DEFAULT 'all' CHECK (target_type IN ('all', 'selective')),
    is_team_work         BOOLEAN NOT NULL DEFAULT FALSE,
    max_score            INTEGER NOT NULL DEFAULT 100 CHECK (max_score > 0),
    due_date             TIMESTAMPTZ NULL,
    template_file_id     UUID NULL,
    is_published         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NULL
);

-- 8. ТАБЛИЦА: assignment_targets (Персональная выдача заданий конкретным студентам)
CREATE TABLE IF NOT EXISTS assignment_targets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    member_id     UUID NOT NULL REFERENCES discipline_members(id) ON DELETE CASCADE,
    assigned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_assignment_member UNIQUE (assignment_id, member_id)
);

-- 9. ТАБЛИЦА: submissions (Сдачи заданий студентами)
CREATE TABLE IF NOT EXISTS submissions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id  UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    team_id        UUID NULL REFERENCES teams(id) ON DELETE SET NULL,
    submitted_by   UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status         VARCHAR(32) NOT NULL DEFAULT 'submitted' CHECK (status IN ('draft', 'submitted', 'in_review', 'graded', 'returned')),
    attempt_number INTEGER NOT NULL DEFAULT 1,
    answer_text    TEXT NULL,
    submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_late        BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at     TIMESTAMPTZ NULL,
    score          NUMERIC(5, 2) NULL,
    feedback       TEXT NULL,
    grader_id      UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    graded_at      TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_submissions_team ON submissions (assignment_id, team_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_submissions_user ON submissions (assignment_id, submitted_by, attempt_number);

-- 10. ТАБЛИЦА: files (Единый реестр файлов, ссылок и документов)
CREATE TABLE IF NOT EXISTS files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id   UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    lesson_id     UUID NULL REFERENCES lessons(id) ON DELETE CASCADE,
    submission_id UUID NULL REFERENCES submissions(id) ON DELETE CASCADE,
    file_type     VARCHAR(32) NOT NULL CHECK (file_type IN ('link', 'document', 'video', 'image', 'archive')),
    url           VARCHAR(1024) NOT NULL,
    file_name     VARCHAR(255) NULL,
    size_bytes    BIGINT NULL,
    mime_type     VARCHAR(128) NULL,
    meta          JSONB NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==============================================================================
-- ВНЕШНИЕ СВЯЗИ ДЛЯ УСТРАНЕНИЯ ЦИКЛИЧЕСКИХ ЗАВИСИМОСТЕЙ
-- ==============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_avatar'
    ) THEN
        ALTER TABLE users 
            ADD CONSTRAINT fk_users_avatar 
            FOREIGN KEY (avatar_id) REFERENCES files(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_disciplines_cover'
    ) THEN
        ALTER TABLE disciplines 
            ADD CONSTRAINT fk_disciplines_cover 
            FOREIGN KEY (cover_file_id) REFERENCES files(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_assignments_template'
    ) THEN
        ALTER TABLE assignments 
            ADD CONSTRAINT fk_assignments_template 
            FOREIGN KEY (template_file_id) REFERENCES files(id) ON DELETE SET NULL;
    END IF;
END $$;
