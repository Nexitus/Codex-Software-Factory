import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skillctl


class SkillRegistryTests(unittest.TestCase):
    def test_registry_is_valid_and_requests_present(self):
        c = skillctl.load_registry()
        ids = {r['id'] for r in c['entries']}
        self.assertTrue({'ui-ux-pro-max','emil-design-eng','screenshot-to-code','graphify','ponytail','loop-library','agent-harness','skill-security-auditor','focused-fix'} <= ids)
        self.assertEqual(next(e for e in c['entries'] if e['id']=='screenshot-to-code')['mode'], 'external')

    def test_ui_ux_and_planner_are_selective(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            p.joinpath('src').mkdir()
            request = {'request':'Add a settings UI', 'plan':{'ui_change':True}}
            ui = {e['id'] for e in skillctl.activate_entries('ui', 'design', request, p)}
            ux = {e['id'] for e in skillctl.activate_entries('ux', 'review', request, p)}
            plan = {e['id'] for e in skillctl.activate_entries('planner', 'plan', request, p)}
            self.assertIn('ui-ux-pro-max', ui)
            self.assertIn('emil-design-eng', ui)
            self.assertNotIn('emil-animate', ui)
            self.assertIn('emil-break-ui', ux)
            self.assertIn('graphify', plan)
            self.assertIn('ponytail', plan)
            self.assertNotIn('screenshot-to-code', ui)

    def test_motion_is_conditional_and_external_apps_never_activated_as_skills(self):
        with tempfile.TemporaryDirectory() as t:
            x = {'request': 'Add animated page transitions', 'plan': {'ui_change':True}}
            selected = {e['id'] for e in skillctl.activate_entries('ui', 'design', x, Path(t))}
            self.assertIn('emil-animate', selected)
            self.assertNotIn('screenshot-to-code', selected)

    def test_tampered_skill_fails_when_enabled(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p/'.factory'/'skills'/'ponytail').mkdir(parents=True)
            doc = p/'.factory'/'skills'/'ponytail'/'SKILL.md'
            doc.write_text('approved content\n')
            entry={'id':'ponytail','source':'demo','path':'skills/ponytail/SKILL.md',
                   'git_blob':skillctl.git_blob_id(doc.read_bytes()),'roles':['planner'],'phases':['plan'],
                   'activation':'always','mode':'prompt'}
            cat={'schema_version':1,'sources':{'demo':{'repo':'demo/demo','url':'https://github.com/demo/demo',
                  'branch':'main','commit':'0'*40,'license':'MIT'}},'entries':[entry]}
            reg=p/'registry.json'; reg.write_text(json.dumps(cat))
            lock=p/'lock.json'; lock.write_text(json.dumps({'sources':cat['sources'],'skills':{'ponytail':{'source':'demo','git_blob':entry['git_blob'],'main_file':'SKILL.md','digest':skillctl.digest_tree(doc.parent)}}}))
            with patch.object(skillctl,'CATALOG',reg),patch.object(skillctl,'LOCK',lock):
                s=skillctl.get_skill_context('planner','plan',{'request':'make app'},p,{'skills':{'enabled':True}},p/'out')
                self.assertIn('approved content',s)
                self.assertTrue((p/'out'/'skills.json').exists())
                doc.write_text('malicious modification\n')
                with self.assertRaises(ValueError):
                    skillctl.get_skill_context('planner','plan',{'request':'make app'},p,{'skills':{'enabled':True}},p/'out2')

    def test_disabled_skills_are_not_loaded(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(skillctl.get_skill_context('ui','review',{},Path(t),{'skills':{'enabled':False}},Path(t)/'out'),'')

    def test_installer_stages_pinned_local_git_source_without_executing_scripts(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            upstream = base/'upstream'
            project = base/'project'
            project.mkdir()
            (upstream/'skills'/'example').mkdir(parents=True)
            source_doc = upstream/'skills'/'example'/'SKILL.md'
            source_doc.write_text('---\nname: example\n---\nCheck acceptance criteria.\n',encoding='utf-8')
            (upstream/'skills'/'example'/'note.md').write_text('Extra guidance\n',encoding='utf-8')
            (upstream/'LICENSE').write_text('Test license\n',encoding='utf-8')
            subprocess.run(['git','init','-q','-b','main'],cwd=upstream,check=True)
            subprocess.run(['git','add','.'],cwd=upstream,check=True)
            subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test','commit','-qm','init'],cwd=upstream,check=True)
            sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
            entry={'id':'example','source':'local','path':'skills/example/SKILL.md','git_blob':skillctl.git_blob_id(source_doc.read_bytes()),
                   'roles':['planner'],'phases':['plan'],'activation':'always','mode':'prompt'}
            source={'repo':'test/local','url':str(upstream),'branch':'main','commit':sha,'license':'MIT'}
            cat={'schema_version':1,'sources':{'local':source},'entries':[entry]}
            catalog=base/'catalog.json'; catalog.write_text(json.dumps(cat))
            lock=base/'lock.json'
            with patch.object(skillctl,'CATALOG',catalog),patch.object(skillctl,'LOCK',lock):
                skillctl.install(project)
                self.assertTrue((project/'.factory'/'skills'/'example'/'note.md').is_file())
                self.assertTrue((project/'.factory'/'skills'/'example'/'UPSTREAM_LICENSE').is_file())
                response=skillctl.get_skill_context('planner','plan',{'request':'test'},project,{'skills':{'enabled':True}},base/'out')
                self.assertIn('Check acceptance criteria.',response)
                with self.assertRaises(ValueError):
                    skillctl.install(project)

    def test_bad_git_blob_is_detected(self):
        self.assertEqual(skillctl.git_blob_id(b'hello\n'), 'ce013625030ba8dba906f756967f9e9ca394464a')

if __name__ == '__main__':
    unittest.main()
