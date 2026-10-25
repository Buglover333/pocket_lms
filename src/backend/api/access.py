"""Object-level access rules shared by all HTTP readers and writers."""
from fastapi import HTTPException
from backend.db import methods
from backend.api.dependencies import check_is_teacher_or_admin

async def course_access(conn, user, course_id):
    course = await methods.get_discipline_by_id(conn, course_id)
    if course is None:
        raise HTTPException(404, "Курс не найден")
    staff = await check_is_teacher_or_admin(conn, user, course_id)
    members = await methods.get_discipline_members(conn, course_id)
    member = next((m for m in members if m['user_id'] == user['id'] and m.get('status') == 'active'), None)
    if not staff and (member is None or course.get('status') != 'published'):
        raise HTTPException(403, "Нет доступа к курсу")
    return course, staff, member

async def material_access(conn, user, material_id):
    material = await methods.get_lesson_by_id(conn, material_id)
    if material is None:
        raise HTTPException(404, "Материал не найден")
    _, staff, _ = await course_access(conn, user, material['discipline_id'])
    if not staff and not material.get('is_published'):
        raise HTTPException(403, "Материал не опубликован")
    return material, staff

async def assignment_access(conn, user, assignment_id):
    assignment = await methods.get_assignment_by_id(conn, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Задание не найдено")
    material, staff = await material_access(conn, user, assignment['lesson_id'])
    if not staff:
        if not assignment.get('is_published'):
            raise HTTPException(403, "Задание не опубликовано")
        if assignment.get('target_type') == 'selective':
            targets = await methods.get_assignment_targets(conn, assignment_id)
            if not any(t['user_id'] == user['id'] for t in targets):
                raise HTTPException(403, "Задание вам не назначено")
    return assignment, material, staff

async def submission_access(conn, user, submission_id):
    submission = await methods.get_submission_by_id(conn, submission_id)
    if submission is None:
        raise HTTPException(404, "Сдача не найдена")
    assignment, material, staff = await assignment_access(conn, user, submission['assignment_id'])
    own = submission['submitted_by'] == user['id']
    teammate = False
    if submission.get('team_id'):
        team = await methods.get_team_by_id(conn, submission['team_id'])
        if team and team['discipline_id'] == material['discipline_id']:
            members = await methods.get_team_members(conn, team['id'])
            teammate = any(m['user_id'] == user['id'] and m.get('status') == 'active' for m in members)
    if not (staff or own or teammate):
        raise HTTPException(403, "Нельзя просматривать чужую работу")
    return submission, assignment, staff

async def file_access(conn, user, file_id, *, write=False):
    record = await methods.get_file_by_id(conn, file_id)
    if record is None:
        raise HTTPException(404, "Файл не найден")
    if record.get("lesson_id") and record.get("submission_id"):
        raise HTTPException(403, "Некорректная привязка файла")
    # Attachments inherit their parent access, even when the caller uploaded them.
    staff = bool(user.get('is_admin'))
    owner = record.get('uploader_id') == user['id']
    if record.get('lesson_id'):
        _, staff = await material_access(conn, user, record['lesson_id'])
        if write and not staff:
            raise HTTPException(403, "Только преподаватель может менять файлы материала")
    elif record.get('submission_id'):
        submission, _, staff = await submission_access(conn, user, record['submission_id'])
        if write and (not owner or submission['status'] not in ('draft', 'returned')):
            if not user.get('is_admin'):
                raise HTTPException(403, "Файлы отправленной работы нельзя изменять")
    elif not (owner or staff):
        raise HTTPException(403, "Нет доступа к файлу")
    return record
