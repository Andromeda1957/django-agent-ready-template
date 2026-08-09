from unittest import TestCase

from tools.dependabot_maintenance import automatic_merge_decision
from tools.dependabot_maintenance import dependency_files_are_bounded
from tools.dependabot_maintenance import quality_gate_state
from tools.dependabot_maintenance import version_bump_is_non_major


class DependabotMaintenanceTests(TestCase):
    def test_accepts_non_major_pinned_version_bumps(self):
        self.assertTrue(version_bump_is_non_major(
            'deps: bump actions/checkout from 7.0.0 to 7.0.1',
        ))
        self.assertTrue(version_bump_is_non_major(
            'deps: bump preview from 0.58b0 to 0.58b1',
        ))

    def test_rejects_major_or_unrecognized_version_bumps(self):
        self.assertFalse(version_bump_is_non_major(
            'deps: bump Django from 6.0.8 to 7.0.0',
        ))
        self.assertFalse(version_bump_is_non_major(
            'deps: update an opaque action SHA',
        ))
        self.assertFalse(version_bump_is_non_major(
            'deps: bump preview from 0.58b0 to 0.64b0',
        ))
        self.assertFalse(version_bump_is_non_major(
            'deps: bump ruff from 0.15.21 to 0.16.0',
        ))

    def test_dependency_file_allowlist_is_bounded(self):
        self.assertTrue(dependency_files_are_bounded([
            {'path': 'requirements-dev.txt'},
            {'path': '.github/workflows/ci.yml'},
        ]))
        self.assertFalse(dependency_files_are_bounded([
            {'path': 'requirements.txt'},
            {'path': 'core/views/pages.py'},
        ]))

    def test_decision_requires_dependabot_main_and_bounded_files(self):
        details = {
            'author': {'login': 'app/dependabot'},
            'baseRefName': 'main',
            'title': 'deps: bump semgrep from 1.169.0 to 1.171.0',
            'files': [{'path': 'requirements-dev.txt'}],
        }
        self.assertTrue(automatic_merge_decision(details).automatic)

        details['author'] = {'login': 'someone-else'}
        self.assertFalse(automatic_merge_decision(details).automatic)

    def test_quality_gate_must_complete_successfully(self):
        self.assertEqual(quality_gate_state([]), 'missing')
        self.assertEqual(quality_gate_state([{
            'name': 'Quality gates',
            'status': 'IN_PROGRESS',
            'conclusion': '',
        }]), 'pending')
        self.assertEqual(quality_gate_state([{
            'name': 'Quality gates',
            'status': 'COMPLETED',
            'conclusion': 'SUCCESS',
        }]), 'success')
        self.assertEqual(quality_gate_state([{
            'name': 'Quality gates',
            'status': 'COMPLETED',
            'conclusion': 'FAILURE',
        }]), 'failure')
