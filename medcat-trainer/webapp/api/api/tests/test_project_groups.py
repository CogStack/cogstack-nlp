"""Unit tests for creating annotation projects from a ProjectGroup."""

from django.test import TestCase, override_settings

from ..models import ConceptDB, ProjectAnnotateEntities, ProjectGroup, Vocabulary
from ..project_groups import (
    GROUP_PROJECTS_OUT_OF_SYNC_MESSAGE,
    create_projects_for_group,
    populate_project_from_group,
    update_projects_for_group,
)
from ._helpers import create_dataset, create_user


@override_settings(MEDIA_ROOT='/tmp/mct-tests-project-groups')
class CreateProjectsForGroupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cdb = ConceptDB(name='pgh_cdb', cdb_file='pgh_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='pgh_vocab', vocab_file='pgh_vocab.dat')
        vocab.save(skip_load=True)
        cls.dataset = create_dataset(name='pgh_ds', file_name='pgh_ds.csv')
        cls.cdb = cdb
        cls.vocab = vocab

    def _group(self, name='pgh-group'):
        return ProjectGroup.objects.create(
            name=name,
            dataset=self.dataset,
            concept_db=self.cdb,
            vocab=self.vocab,
            cuis='',
            description='shared',
        )

    def test_populate_copies_group_settings_and_members(self):
        admin = create_user(username='pgh-admin')
        annotator = create_user(username='pgh-ann')
        group = self._group()
        proj = populate_project_from_group(
            ProjectAnnotateEntities(),
            group,
            annotator,
            [admin],
            [self.cdb],
            [],
            [],
        )
        self.assertEqual(proj.name, 'pgh-group - pgh-ann')
        self.assertEqual(proj.description, 'shared')
        self.assertEqual(proj.group_id, group.id)
        self.assertEqual(proj.dataset_id, self.dataset.id)
        members = set(proj.members.all())
        self.assertEqual(members, {admin, annotator})
        self.assertEqual(list(proj.cdb_search_filter.all()), [self.cdb])

    def test_create_projects_for_group_uses_group_m2m_when_lists_omitted(self):
        admin = create_user(username='pgh-admin2')
        annotator = create_user(username='pgh-ann2')
        group = self._group(name='pgh-m2m')
        group.administrators.add(admin)
        group.annotators.add(annotator)
        group.cdb_search_filter.add(self.cdb)

        created = create_projects_for_group(group)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].name, 'pgh-m2m - pgh-ann2')
        self.assertIn(admin, created[0].members.all())
        self.assertIn(annotator, created[0].members.all())

    def test_update_raises_when_project_count_does_not_match_annotators(self):
        group = self._group(name='pgh-sync')
        annotator = create_user(username='pgh-ann3')
        with self.assertRaisesMessage(ValueError, GROUP_PROJECTS_OUT_OF_SYNC_MESSAGE):
            update_projects_for_group(group, [annotator], [], [], [], [])
