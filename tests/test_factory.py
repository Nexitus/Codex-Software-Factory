import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import factory


class PolicyTests(unittest.TestCase):
    def test_fail_on_missing_gates(self):
        cfg = factory.read_json(factory.ROOT / 'factory.config.json')
        cfg['required_gates'] = []
        with self.assertRaises(factory.FactoryFailure):
            factory.ensure_config(cfg)

    def test_fail_on_review_without_evidence(self):
        self.assertEqual(factory.review_blockers(
            {'security': {'verdict': 'fail', 'findings': [], 'checks': [], 'limitations': []}},
            {'tests': {'pass': True}}, ['security']), ['review:security:fail'])

    def test_fail_on_invalid_review_that_claims_pass(self):
        with self.assertRaises(factory.FactoryFailure):
            factory.parse_result('review', {'verdict': 'pass', 'findings': [
                {'id': 'S1', 'severity': 'high', 'file': 'auth.py', 'evidence': 'no access control', 'remediation': 'add authz'}
            ], 'checks': [], 'limitations': []})

    def test_not_applicable_is_blocker(self):
        r = {'testing': {'verdict': 'not_applicable', 'findings': [], 'checks': [], 'limitations': []}}
        self.assertEqual(factory.review_blockers(r, {}, ['testing']), ['review:testing:not_applicable'])

    def test_protected_file_mutation_fails(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'AGENTS.md').write_text('policy v1')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Mock', '-c', 'user.email=mock@example.test', 'commit', '-qm', 'base'], cwd=root, check=True)
            original = factory.protected_snapshot(root)
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
            (root / 'AGENTS.md').write_text('policy v2')
            with self.assertRaises(factory.FactoryFailure):
                factory.assert_protected(root, original, head)

    def test_supervisor_event_authority_module_is_protected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            authority = root / 'app' / 'events.py'
            authority.parent.mkdir()
            authority.write_text('emit = True\n', encoding='utf-8')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Mock', '-c', 'user.email=mock@example.test', 'commit', '-qm', 'base'], cwd=root, check=True)
            original = factory.protected_snapshot(root)
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
            authority.write_text('emit = False\n', encoding='utf-8')
            with self.assertRaises(factory.FactoryFailure):
                factory.assert_protected(root, original, head)

    def test_install_merges_without_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'AGENTS.md').write_text('Existing instructions\n')
            (root / '.gitignore').write_text('node_modules/\n')
            installer = factory.ROOT / 'install.py'
            result = subprocess.run([sys.executable, str(installer), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Existing instructions', (root / 'AGENTS.md').read_text())
            self.assertIn('Software Factory Instructions', (root / 'AGENTS.md').read_text())
            self.assertIn('node_modules/', (root / '.gitignore').read_text())
            self.assertTrue((root / 'factory.py').exists())
            self.assertTrue((root / 'app' / 'server.py').exists())
            subprocess.run(['git', 'add', '-A'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=InstallTest', '-c', 'user.email=install@example.test', 'commit', '-qm', 'installed scaffold'], cwd=root, check=True)
            help_result = subprocess.run([sys.executable, str(root / 'factory.py'), '--help'], capture_output=True, text=True)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            dry_run = subprocess.run([sys.executable, str(root / 'factory.py'), '--idea', 'safe installation smoke',
                                      '--project', str(root), '--config', str(root / 'factory.config.json'), '--dry-run'],
                                     capture_output=True, text=True)
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertIn('DRY RUN:', dry_run.stdout)
            again = subprocess.run([sys.executable, str(installer), str(root)], capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)

    def test_install_refuses_existing_app_directory_without_copying(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'app').mkdir()
            (root / 'app' / 'keep.py').write_text('KEEP = True\n', encoding='utf-8')
            result = subprocess.run([sys.executable, str(factory.ROOT / 'install.py'), str(root)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('app', result.stderr)
            self.assertFalse((root / 'factory.py').exists())
            self.assertEqual((root / 'app' / 'keep.py').read_text(encoding='utf-8'), 'KEEP = True\n')

    def test_complete_mocked_repair_loop(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            repo = root / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
            (repo / '.gitignore').write_text('.factory/\n', encoding='utf-8')
            (repo / 'spec.md').write_text('Make a widget.', encoding='utf-8')
            subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
            subprocess.run(['git', '-c', 'user.name=Mock', '-c', 'user.email=mock@example.test', 'commit', '-qm', 'base'], cwd=repo, check=True)
            cfg = factory.read_json(factory.ROOT / 'factory.config.json')
            cfg['providers'] = {k: 'codex' for k in cfg['providers']}
            cfg['models'] = {k: ('gpt-6-sol' if k in factory.ORCHESTRATORS else 'gpt-6-luna') for k in cfg['providers']}
            cfg['required_gates'] = ['tests']
            cfg['commands'] = {'tests': [[sys.executable, '-c', "import pathlib; assert 'FIXED = True' in pathlib.Path('app.py').read_text()"]]}
            cfg['max_review_rounds'] = 2
            real_run = subprocess.run

            def provider_stub(argv, **kwargs):
                if Path(argv[0]).name.lower() != 'codex':
                    return real_run(argv, **kwargs)
                prompt = kwargs.get('input', '')
                repo = Path(kwargs['cwd'])
                if 'ROLE: planner' in prompt:
                    data = {'summary': 'mock plan', 'ui_change': False, 'acceptance_criteria': [{'id':'A1','description':'widget','verification':'test gate'}], 'work_items':[{'id':'W1','description':'build widget','verification':'test gate'}], 'assumptions':[], 'risks':[]}
                elif 'ROLE: build_orchestrator' in prompt:
                    data = {'instructions':'implement minimal change, repair when blocked', 'verification_focus':['test gate'], 'risks':[]}
                elif 'PHASE: design' in prompt:
                    data = {'guidance':['add tests'], 'checks':['verify widget'], 'risks':[], 'blocking_questions':[]}
                elif 'ROLE: builder' in prompt:
                    if 'PHASE: repair' in prompt:
                        (repo / 'app.py').write_text('FIXED = True\n')
                    else:
                        (repo / 'app.py').write_text('FIXED = False\n')
                    data = {'summary':'implemented', 'files_changed':['app.py'], 'tests_added':['mock gate'], 'unresolved':[]}
                else:
                    fixed = 'FIXED = True' in (repo / 'app.py').read_text()
                    data = {'verdict': 'pass' if fixed else 'fail', 'findings': [] if fixed else [{'id':'T1', 'severity':'high', 'file':'app.py', 'evidence':'not fixed', 'remediation':'fix'}], 'checks':['mock'], 'limitations':[]}
                output_path = Path(argv[argv.index('--output-last-message') + 1])
                output_path.write_text(json.dumps(data), encoding='utf-8')
                return subprocess.CompletedProcess(argv, 0, '', '')

            with patch('factory.subprocess.run', side_effect=provider_stub):
                result = factory.do_work(repo / 'spec.md', repo, cfg, repo / '.factory' / 'runs' / 'mock', False)
            self.assertEqual(result, 0)
            report = factory.read_json(repo / '.factory' / 'runs' / 'mock' / 'DELIVERY.json')
            self.assertEqual(report['status'], 'verified_candidate')
            self.assertEqual(report['review_rounds'], 2)
            self.assertTrue((repo / 'app.py').exists())
            first = factory.read_json(repo / '.factory' / 'runs' / 'mock' / 'review-round-01' / 'gates.json')
            self.assertFalse(first['tests']['pass'])
            second = factory.read_json(repo / '.factory' / 'runs' / 'mock' / 'review-round-02' / 'gates.json')
            self.assertTrue(second['tests']['pass'])


class StructuredOutputTests(unittest.TestCase):
    def test_passing_review_requires_actual_checks(self):
        with self.assertRaises(factory.FactoryFailure):
            factory.parse_result('review', {'verdict':'pass', 'findings':[], 'checks':[], 'limitations':[]})

    def test_failed_gate_records_error_excerpt(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            result = factory.run_gate('lint', [[sys.executable, '-c', "print('failing line'); raise SystemExit(17)"]], root, root, 4)
            self.assertFalse(result['pass'])
            self.assertEqual(result['commands'][0]['exit_code'], 17)
            self.assertIn('failing line', result['commands'][0]['log_excerpt'])
            self.assertTrue(Path(result['commands'][0]['log_file']).exists())

    def test_config_gate_rejects_no_op_placeholders(self):
        config = factory.read_json(factory.ROOT/'factory.config.json')
        config['commands']['tests'] = [['true']]
        with self.assertRaises(factory.FactoryFailure):
            factory.ensure_config(config)

    def test_codex_builder_gets_workspace_write_and_review_read_only(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(['git', 'init', '-q'],cwd=root,check=True)
            cfg = factory.read_json(factory.ROOT/'factory.config.json')
            cfg['providers'] = {k:'codex' for k in cfg['providers']}
            real_run = subprocess.run

            def provider_stub(argv, **kwargs):
                if Path(argv[0]).name.lower() != 'codex':
                    return real_run(argv, **kwargs)
                prompt = kwargs.get('input', '')
                output = {'summary':'ok','files_changed':['a.py'],'tests_added':['t.py'],'unresolved':[]} if 'ROLE: builder' in prompt else {'verdict':'pass','findings':[],'checks':['inspected a.py line 1'],'limitations':[]}
                Path(argv[argv.index('--output-last-message') + 1]).write_text(json.dumps(output), encoding='utf-8')
                return subprocess.CompletedProcess(argv, 0, '', '')

            with patch('factory.subprocess.run', side_effect=provider_stub):
                builder = factory.execute_agent('builder','build',{},cfg,root,root/'b')
                reviewer = factory.execute_agent('security','review',{},cfg,root,root/'r')
            self.assertEqual(builder['summary'],'ok')
            self.assertEqual(reviewer['verdict'],'pass')
            self.assertIn('mutating=True',(root/'b'/'command.txt').read_text())
            self.assertIn('mutating=False',(root/'r'/'command.txt').read_text())

class AdversarialRoutingTests(unittest.TestCase):
    def setUp(self):
        self.config = factory.read_json(factory.ROOT / 'factory.config.json')
        self.config['commands']['tests'] = [[sys.executable, '-c', 'pass']]
        self.config['commands']['lint'] = [[sys.executable, '-c', 'pass']]
        self.config['commands']['security'] = [[sys.executable, '-c', 'pass']]
        self.config['commands']['build'] = [[sys.executable, '-c', 'pass']]

    def test_no_worker_can_be_premium(self):
        for role in factory.WORKERS:
            cfg = json.loads(json.dumps(self.config))
            provider = cfg['providers'][role]
            cfg['models'][role] = 'gpt-6-sol' if provider == 'codex' else 'claude-opus-5-5'
            with self.subTest(role=role), self.assertRaises(factory.FactoryFailure):
                factory.ensure_config(cfg)

    def test_no_orchestrator_can_be_worker_tier(self):
        for role in factory.ORCHESTRATORS:
            cfg = json.loads(json.dumps(self.config))
            provider = cfg['providers'][role]
            cfg['models'][role] = 'gpt-6-luna' if provider == 'codex' else 'claude-haiku-5-5'
            with self.subTest(role=role), self.assertRaises(factory.FactoryFailure):
                factory.ensure_config(cfg)

    def test_missing_or_unknown_model_fails_closed(self):
        for model in (None, '', 'sonnet', 'default', 'gpt-6-astra'):
            cfg = json.loads(json.dumps(self.config))
            cfg['models']['builder'] = model
            with self.subTest(model=model), self.assertRaises(factory.FactoryFailure):
                factory.ensure_config(cfg)
        cfg = json.loads(json.dumps(self.config))
        del cfg['providers']['build_orchestrator']
        with self.assertRaises(factory.FactoryFailure):
            factory.ensure_config(cfg)

    def test_all_role_models_are_valid(self):
        factory.ensure_config(self.config)
        for role in factory.ALL_ROLES:
            tier = 'orchestrator' if role in factory.ORCHESTRATORS else 'worker'
            self.assertIn(self.config['models'][role], factory.ALLOWED_MODELS[self.config['providers'][role]][tier])

    def test_build_dispatch_schema_rejects_invalid_handoff(self):
        with self.assertRaises(factory.FactoryFailure):
            factory.parse_result('orchestration', {'instructions':'', 'verification_focus':[], 'risks':[]})
        with self.assertRaises(factory.FactoryFailure):
            factory.parse_result('orchestration', {'instructions':'build it', 'verification_focus':[], 'risks':[], 'bypass_gates':True})

    def test_strict_schema_rejects_extra_review_keys(self):
        with self.assertRaises(factory.FactoryFailure):
            factory.parse_result('review', {'verdict':'pass','findings':[], 'checks':['inspected'], 'limitations':[], 'approve_despite_missing_tests':True})

    def test_fingerprint_detects_untracked_and_tracked_changes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(['git','init','-q'],cwd=root,check=True)
            (root/'a.txt').write_text('A')
            subprocess.run(['git','add','a.txt'],cwd=root,check=True)
            original=factory.source_fingerprint(root)
            (root/'a.txt').write_text('B')
            self.assertNotEqual(original,factory.source_fingerprint(root))
            (root/'a.txt').write_text('A')
            (root/'b.txt').write_text('new')
            self.assertNotEqual(original,factory.source_fingerprint(root))

    def test_model_flag_is_explicit_per_role_and_phase(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(['git','init','-q'],cwd=root,check=True)
            cfg=json.loads(json.dumps(self.config))
            cfg['providers']={role:'codex' for role in factory.ALL_ROLES}
            cfg['models']={role:('gpt-6-sol' if role in factory.ORCHESTRATORS else 'gpt-6-luna') for role in factory.ALL_ROLES}
            real_run = subprocess.run

            def provider_stub(argv, **kwargs):
                if Path(argv[0]).name.lower() != 'codex':
                    return real_run(argv, **kwargs)
                prompt = kwargs.get('input', '')
                if '--model' not in argv:
                    return subprocess.CompletedProcess(argv, 6, '', 'model missing')
                model = argv[argv.index('--model') + 1]
                role = prompt.split('ROLE: ')[1].splitlines()[0]
                expected = 'gpt-6-sol' if role in ('planner', 'build_orchestrator') else 'gpt-6-luna'
                if model != expected:
                    return subprocess.CompletedProcess(argv, 7, '', 'wrong model')
                data = {'instructions':'implement', 'verification_focus':['tests'], 'risks':[]} if role == 'build_orchestrator' else {'summary':'ok', 'files_changed':['a.py'], 'tests_added':['t.py'], 'unresolved':[]}
                Path(argv[argv.index('--output-last-message') + 1]).write_text(json.dumps(data), encoding='utf-8')
                return subprocess.CompletedProcess(argv, 0, '', '')

            with patch('factory.subprocess.run', side_effect=provider_stub):
                high=factory.execute_agent('build_orchestrator','dispatch',{},cfg,root,root/'high')
                low=factory.execute_agent('builder','build',{},cfg,root,root/'low')
            self.assertEqual(high['instructions'],'implement')
            self.assertEqual(low['summary'],'ok')
            self.assertIn('model=gpt-6-sol', (root/'high'/'command.txt').read_text())
            self.assertIn('model=gpt-6-luna', (root/'low'/'command.txt').read_text())

class GateIntegrityAdversarialTests(unittest.TestCase):
    def test_npm_test_script_bypass_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'package.json').write_text(json.dumps({'scripts':{'test':'vitest run','lint':'eslint .'}}))
            cfg=factory.read_json(factory.ROOT/'examples/config-node.json')
            baseline=factory.gate_entrypoints(cfg,root)
            self.assertEqual(baseline['package.json:scripts:test'],'vitest run')
            (root/'package.json').write_text(json.dumps({'scripts':{'test':'echo ALL PASSED','lint':'eslint .'}}))
            with self.assertRaises(factory.FactoryFailure):
                factory.assert_gate_integrity(cfg,root,baseline,False)

    def test_local_security_script_rewrite_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'security-check.py').write_text('raise SystemExit(1)')
            cfg=factory.read_json(factory.ROOT/'factory.config.json')
            cfg['commands']['security']=[['python','security-check.py']]
            baseline=factory.gate_entrypoints(cfg,root)
            self.assertIn('file:security-check.py',baseline)
            (root/'security-check.py').write_text('raise SystemExit(0)')
            with self.assertRaises(factory.FactoryFailure):
                factory.assert_gate_integrity(cfg,root,baseline,False)

    def test_unchanged_gate_script_passes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'package.json').write_text(json.dumps({'scripts':{'test':'vitest run'}}))
            cfg=factory.read_json(factory.ROOT/'examples/config-node.json')
            baseline=factory.gate_entrypoints(cfg,root)
            (root/'new-component.ts').write_text('export const x = 1;')
            factory.assert_gate_integrity(cfg,root,baseline,False)

class ClaudeModelEnforcementTests(unittest.TestCase):
    def test_claude_invocations_explicitly_choose_opus_for_lead_and_haiku_for_worker(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            subprocess.run(['git','init','-q'],cwd=root,check=True)
            cfg=factory.read_json(factory.ROOT/'factory.config.json')
            cfg['providers'] = {role: 'claude' for role in factory.ALL_ROLES}
            cfg['models'] = {role: ('claude-opus-5-5' if role in factory.ORCHESTRATORS else 'claude-haiku-5-5') for role in factory.ALL_ROLES}
            real_run = subprocess.run

            def provider_stub(argv, **kwargs):
                if Path(argv[0]).name.lower() != 'claude':
                    return real_run(argv, **kwargs)
                if '--model' not in argv:
                    return subprocess.CompletedProcess(argv, 11, '', 'model missing')
                model = argv[argv.index('--model') + 1]
                prompt = argv[-1]
                role = prompt.split('ROLE: ')[1].splitlines()[0]
                if role == 'build_orchestrator' and model == 'claude-opus-5-5':
                    result = {'instructions':'make minimal patch','verification_focus':['unit tests'],'risks':[]}
                elif role == 'builder' and model == 'claude-haiku-5-5':
                    result = {'summary':'patched','files_changed':['app.py'],'tests_added':['test_app.py'],'unresolved':[]}
                else:
                    return subprocess.CompletedProcess(argv, 14, '', 'unexpected role or model')
                return subprocess.CompletedProcess(argv, 0, json.dumps({'structured_output':result}), '')

            with patch('factory.subprocess.run', side_effect=provider_stub):
                high=factory.execute_agent('build_orchestrator','dispatch',{},cfg,root,root/'dispatch')
                low=factory.execute_agent('builder','build',{},cfg,root,root/'build')
            self.assertEqual(high['instructions'],'make minimal patch')
            self.assertEqual(low['summary'],'patched')
            self.assertIn('model=claude-opus-5-5', (root/'dispatch'/'command.txt').read_text())
            self.assertIn('model=claude-haiku-5-5', (root/'build'/'command.txt').read_text())

if __name__ == "__main__":
    unittest.main()
