import importlib.util, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get('POIGHT_PYTHON', sys.executable)
CLI = ROOT / 'scripts' / 'project.py'

def invoke(*args, cwd=None, env=None):
    return subprocess.run([PY, str(CLI), *args], cwd=cwd, env=env, text=True, capture_output=True)

class ScaffoldTests(unittest.TestCase):
    def test_paths_with_spaces_and_chinese_cwd_arbitrary(self):
        with tempfile.TemporaryDirectory(prefix='Poight 空格 ') as temp:
            result = invoke('status', cwd=temp)
            self.assertIn(str(ROOT), result.stdout)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_candidate_live_guard_no_fallback(self):
        spec = importlib.util.spec_from_file_location('project_helper', CLI)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'index.html').touch()
            self.assertFalse(module.candidate_ready(Path(temp)), 'live must never satisfy candidate gate')
        source = CLI.read_text()
        self.assertIn("'localhost'", source)
        self.assertIn("'--candidate'", source)
        self.assertIn('if not candidate_ready(ROOT)', source)

    def test_missing_interpreter_is_clear(self):
        env = os.environ.copy(); env['POIGHT_PYTHON'] = '/definitely/missing/python'
        result = invoke('check', cwd='/tmp', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('POIGHT_PYTHON不可执行或不存在', result.stdout + result.stderr)

    def test_ignore_safety_and_source_allow(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(['git','init','-q',temp], check=True)
            subprocess.run(['git','-C',temp,'config','core.excludesFile','/dev/null'], check=True)
            subprocess.run(['cp',str(ROOT/'.gitignore'),temp+'/.gitignore'], check=True)
            subprocess.run(['git','-C',temp,'add','.gitignore'], check=True)
            cases = ['firmware.gba','.env','service.key','发布清单.json','素材/角色库/原始/portrait.png','thirdparty/.git/config']
            for rel in cases:
                (Path(temp)/rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(temp)/rel).touch()
                probe = subprocess.run(['git','-C',temp,'check-ignore','--no-index','-q',rel])
                self.assertEqual(probe.returncode, 0, f'not ignored: {rel}')
            (Path(temp)/'游戏数据.py').touch()
            probe = subprocess.run(['git','-C',temp,'check-ignore','--no-index','-q','游戏数据.py'])
            self.assertEqual(probe.returncode, 1, 'source unexpectedly ignored')

    def test_no_remote(self):
        result = subprocess.run(['git','-C',str(ROOT),'remote','-v'], text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), '')

if __name__ == '__main__': unittest.main()
