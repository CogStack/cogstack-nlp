"""Tests for the metrics view endpoints in api.views.

The heavy lifting (`calculate_metrics`) is a background task backed by MedCAT,
so it is mocked here. Report retrieval/removal is exercised against real
`background_task` Task / CompletedTask rows and `ProjectMetrics` model rows.
"""

import json
import os
from unittest.mock import MagicMock, patch

from background_task.models import CompletedTask, Task
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework.test import APIClient

from ..models import ProjectMetrics
from ._helpers import create_basic_project, create_user


MEDIA_ROOT = '/tmp/mct-tests-metrics'


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_task(verbose_name, creator, model=Task, queue='metrics', last_error=''):
    return model.objects.create(
        task_name='api.metrics.calculate_metrics',
        task_params='[[], {}]',
        task_hash='hash',
        run_at=timezone.now(),
        queue=queue,
        verbose_name=verbose_name,
        last_error=last_error,
        creator=creator,
    )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MetricsJobsPostTests(TestCase):
    def setUp(self):
        self.user = create_user(username='metrics-poster')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='metrics-proj')

    def test_post_submits_metrics_job(self):
        fake_job = MagicMock()
        fake_job.id = 4242
        with patch('api.views.calculate_metrics', return_value=fake_job) as mock_calc:
            resp = self.client.post(
                '/api/metrics-job/',
                {'projectIds': str(self.project.id)},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['metrics_job_id'], 4242)
        self.assertTrue(resp.json()['metrics_job_name'].startswith('metrics-'))
        mock_calc.assert_called_once()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MetricsJobsGetTests(TestCase):
    def setUp(self):
        self.user = create_user(username='metrics-getter')
        self.client = _auth_client(self.user)

    def test_get_returns_empty_when_no_jobs(self):
        resp = self.client.get('/api/metrics-job/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['reports'], [])

    def test_get_lists_running_and_completed_reports(self):
        _make_task('metrics-1_2-2024', self.user, model=Task)
        _make_task('metrics-3-2024', self.user, model=CompletedTask)
        ProjectMetrics.objects.create(
            report_name_generated='metrics-3-2024',
            report_name='Friendly Name',
        )

        resp = self.client.get('/api/metrics-job/')
        self.assertEqual(resp.status_code, 200)
        reports = resp.json()['reports']
        self.assertEqual(len(reports), 2)

        running = next(r for r in reports if r['report_name_generated'] == 'metrics-1_2-2024')
        self.assertEqual(running['status'], 'pending')
        self.assertEqual(running['projects'], ['1', '2'])
        self.assertEqual(running['created_user'], self.user.username)

        comp = next(r for r in reports if r['report_name_generated'] == 'metrics-3-2024')
        self.assertEqual(comp['status'], 'complete')
        self.assertEqual(comp['report_name'], 'Friendly Name')

    def test_get_marks_failed_completed_task(self):
        _make_task('metrics-9-2024', self.user, model=CompletedTask, last_error='boom\ntraceback')
        resp = self.client.get('/api/metrics-job/')
        self.assertEqual(resp.status_code, 200)
        comp = resp.json()['reports'][0]
        self.assertEqual(comp['status'], 'Failed')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ViewMetricsTests(TestCase):
    def setUp(self):
        self.user = create_user(username='metrics-viewer')
        self.client = _auth_client(self.user)
        self.completed = _make_task('metrics-5-2024', self.user, model=CompletedTask)
        self.pm = ProjectMetrics.objects.create(
            report_name_generated='metrics-5-2024',
            report_name='Original Name',
        )
        self.pm.report.save('metrics-5-2024.json', ContentFile(json.dumps({'concept_summary': []})))

    def tearDown(self):
        if self.pm.report and os.path.isfile(self.pm.report.path):
            os.remove(self.pm.report.path)

    def test_get_returns_report_contents(self):
        resp = self.client.get(f'/api/metrics/{self.completed.id}/')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()['results']
        self.assertEqual(results['report_name'], 'Original Name')
        self.assertIn('concept_summary', results)

    def test_put_renames_report(self):
        resp = self.client.put(
            f'/api/metrics/{self.completed.id}/',
            {'report_name': 'Renamed Report'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.pm.refresh_from_db()
        self.assertEqual(self.pm.report_name, 'Renamed Report')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RemoveMetricsJobTests(TestCase):
    def setUp(self):
        self.user = create_user(username='metrics-remover')
        self.client = _auth_client(self.user)

    def test_delete_completed_report_removes_task_and_metrics(self):
        completed = _make_task('metrics-7-2024', self.user, model=CompletedTask)
        pm = ProjectMetrics.objects.create(
            report_name_generated='metrics-7-2024',
            report_name='To Delete',
        )
        pm.report.save('metrics-7-2024.json', ContentFile(json.dumps({})))
        report_path = pm.report.path

        resp = self.client.delete(f'/api/metrics-job/{completed.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CompletedTask.objects.filter(id=completed.id).exists())
        self.assertFalse(ProjectMetrics.objects.filter(id=pm.id).exists())
        self.assertFalse(os.path.isfile(report_path))
