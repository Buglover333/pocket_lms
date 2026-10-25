"""Object access and S3 protocol checks against a dedicated PostgreSQL database."""
import unittest
from unittest.mock import patch
from uuid import uuid4
import test_api as fixtures
from backend.api.security import make_token

class APIReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.APIContractTests.setUpClass.__func__(cls)
    setUp = fixtures.APIContractTests.setUp
    create_user = fixtures.APIContractTests.create_user
    assert_error = fixtures.APIContractTests.assert_error
    def cleanup_rows(self):
        for uid in self.user_ids:
            self.db.execute('DELETE FROM files WHERE uploader_id = %s', (uid,))
        fixtures.APIContractTests.cleanup_rows(self)

    def setup_course(self):
        self.course = self.db.execute("INSERT INTO disciplines (author_id,title,status,invite_code) VALUES (%s,'Курс','published',%s) RETURNING id", (self.other['id'], uuid4().hex)).fetchone()['id']
        self.member = self.db.execute("INSERT INTO discipline_members (discipline_id,user_id,role) VALUES (%s,%s,'student') RETURNING id", (self.course,self.user['id'])).fetchone()['id']
        self.lesson = self.db.execute("INSERT INTO lessons (discipline_id,title) VALUES (%s,'Урок') RETURNING id", (self.course,)).fetchone()['id']
        self.assignment = self.db.execute("INSERT INTO assignments (lesson_id,title,description_markdown) VALUES (%s,'Задание','Описание') RETURNING id", (self.lesson,)).fetchone()['id']
        self.teacher_headers = {'Authorization':'Bearer '+make_token(self.other['id'])}

    def submission(self, user=None, **extra):
        body = dict(assignment_id=str(self.assignment), submitted_by=str((user or self.user)['id']), answer_text='Работа')
        body.update(extra)
        return self.client.post('/submit_work',json=body,headers=self.headers)

    def test_settings_only_allow_names_and_persist(self):
        for field,value in [('password_hash','fake'),('email','new@example.com'),('is_admin',True),('is_active',False)]:
            self.assert_error(self.client.patch('/update_settings',json={field:value},headers=self.headers),422)
        for value in ('', '   ', None):
            self.assert_error(self.client.patch('/update_settings',json={'first_name':value},headers=self.headers),422)
        r=self.client.patch('/update_settings',json={'first_name':' Анна '},headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['first_name'],'Анна')
        self.assertEqual(self.db.execute('SELECT first_name FROM users WHERE id=%s',(self.user['id'],)).fetchone()['first_name'],'Анна')

    def test_nonmembers_cannot_read_materials_assignments_calendar_or_groups(self):
        self.setup_course()
        outsider=self.create_user();headers={'Authorization':'Bearer '+make_token(outsider['id'])}
        for path,params in [('/get_materials',{'course_id':self.course}),('/get_material_data',{'material_id':self.lesson}),('/get_assignments',{'lesson_id':self.lesson}),('/get_assignment_data',{'assignment_id':self.assignment}),('/get_calendar',{'course_id':self.course}),('/get_groups',{'course_id':self.course})]:
            with self.subTest(path=path):
                self.assert_error(self.client.get(path,params=params,headers=headers),403)

    def test_drafts_are_hidden_from_student_but_visible_to_teacher(self):
        self.setup_course()
        self.db.execute('UPDATE lessons SET is_published=false WHERE id=%s',(self.lesson,))
        r=self.client.get('/get_materials',params={'course_id':self.course},headers=self.headers)
        self.assertEqual(r.json()['items'],[])
        self.assert_error(self.client.get('/get_material_data',params={'material_id':self.lesson},headers=self.headers),403)
        r=self.client.get('/get_material_data',params={'material_id':self.lesson},headers=self.teacher_headers)
        self.assertEqual(r.status_code,200,r.text)
        r=self.client.patch('/update_material',params={'material_id':self.lesson},json={'is_published':True},headers=self.teacher_headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.get('/get_material_data',params={'material_id':self.lesson},headers=self.headers).status_code,200)

    def test_selective_assignment_and_submission_require_target(self):
        self.setup_course()
        self.db.execute("UPDATE assignments SET target_type='selective' WHERE id=%s",(self.assignment,))
        self.assert_error(self.submission(),403)
        r=self.client.get('/get_assignments',params={'lesson_id':self.lesson},headers=self.headers)
        self.assertEqual(r.json()['items'],[])
        self.db.execute('INSERT INTO assignment_targets (assignment_id,member_id) VALUES (%s,%s)',(self.assignment,self.member))
        self.assertEqual(self.submission().status_code,201)

    def test_submissions_are_scoped_to_selected_student(self):
        self.setup_course()
        own=self.submission();self.assertEqual(own.status_code,201,own.text)
        other_student=self.create_user()
        self.db.execute("INSERT INTO discipline_members (discipline_id,user_id,role) VALUES (%s,%s,'student')",(self.course,other_student['id']))
        other_sub=self.db.execute('INSERT INTO submissions (assignment_id,submitted_by) VALUES (%s,%s) RETURNING id',(self.assignment,other_student['id'])).fetchone()['id']
        r=self.client.get('/get_submissions',params={'assignment_id':self.assignment},headers=self.headers)
        self.assertEqual([x['id'] for x in r.json()['items']],[own.json()['id']])
        self.assert_error(self.client.get('/get_submissions',params={'assignment_id':self.assignment,'student_id':other_student['id']},headers=self.headers),403)
        self.assert_error(self.client.get('/get_submission_data',params={'submission_id':other_sub},headers=self.headers),403)
        r=self.client.get('/get_submissions',params={'assignment_id':self.assignment,'student_id':other_student['id']},headers=self.teacher_headers)
        self.assertEqual([x['id'] for x in r.json()['items']],[str(other_sub)])

    def test_nonmember_cannot_submit_or_read_file(self):
        self.setup_course()
        self.db.execute('DELETE FROM discipline_members WHERE id=%s',(self.member,))
        self.assert_error(self.submission(),403)
        file_id=self.db.execute("INSERT INTO files (uploader_id,lesson_id,file_type,url) VALUES (%s,%s,'document','https://example.com/a') RETURNING id",(self.other['id'],self.lesson)).fetchone()['id']
        self.assert_error(self.client.get('/get_file',params={'file_id':file_id},headers=self.headers),403)
        self.assert_error(self.client.get('/get_file_download',params={'file_id':file_id},headers=self.headers),403)

    def test_submission_file_is_private_and_attached_atomically(self):
        self.setup_course()
        fid=self.db.execute("INSERT INTO files (uploader_id,file_type,url) VALUES (%s,'document','https://example.com/a') RETURNING id",(self.user['id'],)).fetchone()['id']
        r=self.submission(file_ids=[str(fid)]);self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(str(self.db.execute('SELECT submission_id FROM files WHERE id=%s',(fid,)).fetchone()['submission_id']),r.json()['id'])
        other_student=self.create_user()
        self.db.execute("INSERT INTO discipline_members (discipline_id,user_id) VALUES (%s,%s)",(self.course,other_student['id']))
        h={'Authorization':'Bearer '+make_token(other_student['id'])}
        self.assert_error(self.client.get('/get_file',params={'file_id':fid},headers=h),403)
        self.assertEqual(self.client.get('/get_file',params={'file_id':fid},headers=self.teacher_headers).status_code,200)

    def test_cannot_attach_foreign_file_or_reuse_it(self):
        self.setup_course()
        fid=self.db.execute("INSERT INTO files (uploader_id,file_type,url) VALUES (%s,'document','https://example.com/a') RETURNING id",(self.other['id'],)).fetchone()['id']
        self.assert_error(self.submission(file_ids=[str(fid)]),403)
        self.assertEqual(self.db.execute('SELECT count(*) AS n FROM submissions WHERE assignment_id=%s',(self.assignment,)).fetchone()['n'],0)

    def test_s3_upload_confirm_download_protocol_and_ownership(self):
        body={'file_name':'report.pdf','file_type':'document','mime_type':'application/pdf','size_bytes':10}
        with patch('backend.api.routers.files.storage.upload_url',return_value=('private-bucket',{'url':'https://storage.example/upload','fields':{'key':'test'}})):
            r=self.client.post('/create_file_upload',json=body,headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        fid=r.json()['file_id']
        params={'file_id':fid}
        self.assert_error(self.client.get('/get_file_download',params=params,headers=self.headers),409)
        with patch('backend.api.routers.files.storage.verify_upload') as verify:
            r=self.client.post('/complete_file_upload',params=params,headers=self.headers)
            self.assertEqual(r.status_code,200,r.text);verify.assert_called_once()
        with patch('backend.api.routers.files.storage.download_url',return_value='https://storage.example/signed') as sign:
            r=self.client.get('/get_file_download',params=params,headers=self.headers)
            self.assertEqual(r.status_code,200,r.text);sign.assert_called_once()
            self.assertEqual(r.json()['expires_in'],300)
            h={'Authorization':'Bearer '+make_token(self.other['id'])}
            self.assert_error(self.client.get('/get_file_download',params=params,headers=h),403)
            self.assertEqual(sign.call_count,1)

    def test_cannot_forge_s3_metadata_or_storage_key(self):
        for body in [dict(file_type='document',url='s3://private/secret'),dict(file_type='document',url='https://example.com',meta={'storage':'s3','bucket':'private','key':'secret','upload_status':'ready'})]:
            self.assert_error(self.client.post('/upload_file',json=body,headers=self.headers),422)
        self.assert_error(self.client.post('/create_file_upload',json={'file_name':'a','file_type':'document','mime_type':'application/pdf','size_bytes':1,'key':'secret'},headers=self.headers),422)

    def test_team_submission_and_grade_visible_to_teammate(self):
        self.setup_course()
        team=self.db.execute("INSERT INTO teams (discipline_id,name) VALUES (%s,'Команда') RETURNING id",(self.course,)).fetchone()['id']
        self.db.execute('UPDATE discipline_members SET team_id=%s WHERE id=%s',(team,self.member))
        teammate=self.create_user()
        self.db.execute("INSERT INTO discipline_members (discipline_id,user_id,team_id) VALUES (%s,%s,%s)",(self.course,teammate['id'],team))
        self.db.execute('UPDATE assignments SET is_team_work=true WHERE id=%s',(self.assignment,))
        r=self.submission(team_id=str(team));self.assertEqual(r.status_code,201,r.text)
        sid=r.json()['id']
        body={'status':'graded','score':101,'grader_id':str(self.other['id'])}
        self.assert_error(self.client.post('/grade_submission',params={'submission_id':sid},json=body,headers=self.teacher_headers),422)
        body['score']=80
        self.assertEqual(self.client.post('/grade_submission',params={'submission_id':sid},json=body,headers=self.teacher_headers).status_code,200)
        h={'Authorization':'Bearer '+make_token(teammate['id'])}
        r=self.client.get('/get_submissions',params={'assignment_id':self.assignment},headers=h)
        self.assertEqual(r.json()['items'][0]['id'],sid)
        r=self.client.get('/get_grades',params={'course_id':self.course},headers=h)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(float(r.json()['items'][0]['score']),80)
        self.db.execute("UPDATE discipline_members SET status='left' WHERE user_id=%s",(teammate['id'],))
        self.assert_error(self.client.get('/get_submission_data',params={'submission_id':sid},headers=h),403)

    def test_foreign_team_cannot_be_used_for_submission(self):
        self.setup_course()
        team=self.db.execute("INSERT INTO teams (discipline_id,name) VALUES (%s,'Не моя команда') RETURNING id",(self.course,)).fetchone()['id']
        self.db.execute('UPDATE assignments SET is_team_work=true WHERE id=%s',(self.assignment,))
        self.assert_error(self.submission(team_id=str(team)),403)

    def test_attachment_cannot_be_claimed_by_second_submission(self):
        self.setup_course()
        fid=self.db.execute("INSERT INTO files (uploader_id,file_type,url) VALUES (%s,'document','https://example.com/a') RETURNING id",(self.user['id'],)).fetchone()['id']
        self.assertEqual(self.submission(file_ids=[str(fid)]).status_code,201)
        self.assert_error(self.submission(file_ids=[str(fid)]),403)
        self.assertEqual(self.db.execute('SELECT count(*) AS n FROM submissions WHERE assignment_id=%s',(self.assignment,)).fetchone()['n'],1)

    def test_s3_size_mismatch_does_not_mark_file_ready(self):
        from fastapi import HTTPException
        body={'file_name':'a.pdf','file_type':'document','mime_type':'application/pdf','size_bytes':10}
        with patch('backend.api.routers.files.storage.upload_url',return_value=('private-bucket',{'url':'https://storage.example/upload','fields':{}})):
            r=self.client.post('/create_file_upload',json=body,headers=self.headers)
        fid=r.json()['file_id']
        with patch('backend.api.routers.files.storage.verify_upload',side_effect=HTTPException(409,'Размер не совпадает')):
            self.assert_error(self.client.post('/complete_file_upload',params={'file_id':fid},headers=self.headers),409)
        record=self.db.execute('SELECT meta FROM files WHERE id=%s',(fid,)).fetchone()
        self.assertEqual(record['meta']['upload_status'],'pending')

    def test_s3_policy_limits_content_type_size_and_expiry(self):
        from backend.services import storage
        from unittest.mock import MagicMock
        client=MagicMock()
        client.generate_presigned_post.return_value={'url':'https://storage.example/upload','fields':{}}
        with patch('backend.services.storage.configuration',return_value=(client,'private-bucket')):
            storage.upload_url('uploads/owner/random','application/pdf')
        call=client.generate_presigned_post.call_args.kwargs
        self.assertEqual(call['ExpiresIn'],300)
        self.assertIn(['content-length-range',1,50*1024*1024],call['Conditions'])
        self.assertIn({'Content-Type':'application/pdf'},call['Conditions'])

    def test_resubmit_sets_submitted_status_on_server(self):
        self.setup_course()
        r=self.submission();self.assertEqual(r.status_code,201,r.text)
        sid=r.json()['id']
        self.db.execute("UPDATE submissions SET status='returned' WHERE id=%s",(sid,))
        r=self.client.post('/resubmit_work',params={'submission_id':sid},json={'status':'in_review','answer_text':'Исправлено'},headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['status'],'submitted')

    def test_one_profile_reader_and_all_delete_routes_remain(self):
        from backend.api.main import app
        paths = app.openapi()['paths']
        self.assertNotIn('/get_settings', paths)
        for path in ('/delete_material', '/delete_assignment', '/delete_group', '/delete_file'):
            self.assertIn('delete', paths[path])
        r = self.client.get('/get_user_info', params={'user_id': self.user['id']}, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['id'], str(self.user['id']))

    def test_grading_requires_score_and_cannot_return_work(self):
        self.setup_course()
        sid = self.submission().json()['id']
        params = {'submission_id': sid}
        body = {'grader_id': str(self.other['id']), 'status': 'graded'}
        for score in (None, -1, 101):
            with self.subTest(score=score):
                self.assert_error(self.client.post('/grade_submission', params=params,
                    json={**body, 'score': score}, headers=self.teacher_headers), 422)
        self.assert_error(self.client.post('/grade_submission', params=params,
            json=body, headers=self.teacher_headers), 422)
        self.assert_error(self.client.post('/grade_submission', params=params,
            json={**body, 'score': 10, 'status': 'returned'}, headers=self.teacher_headers), 422)
        self.assertEqual(self.db.execute('SELECT status FROM submissions WHERE id=%s', (sid,)).fetchone()['status'], 'submitted')
        for score in (0, 100):
            r = self.client.post('/grade_submission', params=params,
                json={**body, 'score': score}, headers=self.teacher_headers)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()['score'], score)
        r = self.client.post('/return_submission', params={**params, 'feedback': 'Исправить ответ'}, headers=self.teacher_headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['status'], 'returned')
        self.assertIsNone(r.json()['score'])
        r = self.client.post('/resubmit_work', params=params, json={'answer_text': 'Исправленный ответ'}, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['status'], 'submitted')

    def test_teacher_can_read_selected_student_grades_but_other_student_cannot(self):
        self.setup_course()
        sid = self.submission().json()['id']
        self.db.execute("UPDATE submissions SET score=75,status='graded' WHERE id=%s", (sid,))
        params = {'course_id': self.course, 'user_id': self.user['id']}
        r = self.client.get('/get_grades', params=params, headers=self.teacher_headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(float(r.json()['items'][0]['score']), 75)
        outsider = self.create_user()
        self.db.execute('INSERT INTO discipline_members (discipline_id,user_id) VALUES (%s,%s)', (self.course, outsider['id']))
        h = {'Authorization': 'Bearer ' + make_token(outsider['id'])}
        self.assert_error(self.client.get('/get_grades', params=params, headers=h), 403)

    def test_grade_list_hides_drafts_and_unassigned_selective_assignments(self):
        self.setup_course()
        params = {'course_id': self.course}
        self.db.execute('UPDATE lessons SET is_published=false WHERE id=%s', (self.lesson,))
        self.assertEqual(self.client.get('/get_grades', params=params, headers=self.headers).json()['items'], [])
        self.db.execute('UPDATE lessons SET is_published=true WHERE id=%s', (self.lesson,))
        self.db.execute("UPDATE assignments SET target_type='selective' WHERE id=%s", (self.assignment,))
        self.assertEqual(self.client.get('/get_grades', params=params, headers=self.headers).json()['items'], [])
        self.db.execute('INSERT INTO assignment_targets (assignment_id,member_id) VALUES (%s,%s)', (self.assignment, self.member))
        self.assertEqual(len(self.client.get('/get_grades', params=params, headers=self.headers).json()['items']), 1)

    def test_course_and_material_list_share_publication_rules(self):
        self.setup_course()
        params = {'course_id': self.course}
        self.db.execute('UPDATE lessons SET is_published=false WHERE id=%s', (self.lesson,))
        for h, count in ((self.headers, 0), (self.teacher_headers, 1)):
            course = self.client.get('/get_course_data', params=params, headers=h)
            materials = self.client.get('/get_materials', params=params, headers=h)
            self.assertEqual(course.status_code, 200, course.text)
            self.assertEqual(materials.status_code, 200, materials.text)
            self.assertEqual(len(course.json()['lessons']), count)
            self.assertEqual(course.json()['lessons'], materials.json()['items'])
        self.db.execute("UPDATE disciplines SET status='draft' WHERE id=%s", (self.course,))
        self.assert_error(self.client.get('/get_course_data', params=params, headers=self.headers), 403)
        self.assertEqual(self.client.get('/get_course_data', params=params, headers=self.teacher_headers).status_code, 200)

    def test_submitted_work_cannot_be_resubmitted_without_return(self):
        self.setup_course()
        sid = self.submission().json()['id']
        self.assert_error(self.client.post('/resubmit_work', params={'submission_id': sid},
            json={'answer_text': 'Замена'}, headers=self.headers), 409)
        self.assertEqual(self.db.execute('SELECT answer_text FROM submissions WHERE id=%s', (sid,)).fetchone()['answer_text'], 'Работа')
