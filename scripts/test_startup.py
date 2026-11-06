import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gateway_startup as gateway
from startup_lock import startup_lock


class StartupTests(unittest.TestCase):
    def run_start(self, status, owners=(), exit_code=None, timeout=240):
        clock = [0.0]
        process = Mock(returncode=exit_code)
        process.poll.return_value = exit_code
        spawn = Mock(return_value=process)
        def probe(_token): return status(clock[0])
        def sleep(seconds): clock[0] += seconds
        with patch.object(gateway, 'gateway_status', side_effect=probe), \
             patch.object(gateway, 'gateway_processes', return_value=list(owners)), \
             patch.object(gateway.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(gateway.time, 'sleep', side_effect=sleep), \
             contextlib.redirect_stdout(io.StringIO()):
            gateway.wait_for_gateway('test-token', 'test/openclaw.mjs', spawn, timeout=timeout)
        return spawn, process, clock[0]

    def test_ready_gateway_is_reused(self):
        spawn, _, elapsed = self.run_start(lambda _: ('ready',''))
        spawn.assert_not_called()
        self.assertEqual(elapsed,0)

    def test_reboot_recovery_longer_than_old_timeout_is_reused(self):
        spawn, _, elapsed = self.run_start(lambda now: ('starting','Recovering sessions') if now < 150 else ('ready',''))
        spawn.assert_not_called()
        self.assertEqual(elapsed,150)

    def test_process_before_listener_binds_is_reused(self):
        spawn, _, _ = self.run_start(lambda now: ('absent','Binding') if now < 20 else ('ready',''), owners=[123])
        spawn.assert_not_called()

    def test_cold_start_spawns_once(self):
        spawn, _, _ = self.run_start(lambda now: ('absent','') if now < 2 else ('starting','') if now < 10 else ('ready',''))
        spawn.assert_called_once()

    def test_launcher_exit_does_not_override_live_recovery(self):
        spawn, _, _ = self.run_start(lambda now: ('absent','') if now < 1 else ('starting','Recovering') if now < 10 else ('ready',''), exit_code=0)
        spawn.assert_called_once()

    def test_actual_exit_is_reported(self):
        with self.assertRaisesRegex(SystemExit,'exited \\(code 1\\)'):
            self.run_start(lambda _: ('absent',''), exit_code=1)

    def test_conflicting_profile_does_not_spawn(self):
        with self.assertRaisesRegex(SystemExit,'different profile'):
            self.run_start(lambda _: ('conflict','different profile'))

    def test_slow_recovery_timeout_keeps_existing_process(self):
        with self.assertRaisesRegex(SystemExit,'left running'):
            self.run_start(lambda _: ('starting','Recovering'), timeout=3)


class ProbeTests(unittest.TestCase):
    def test_recovering_database_is_starting_not_missing(self):
        with patch.object(gateway,'get_json',side_effect=[(200,{'ok':True,'status':'live'}),
            (200,{'data':[{'id':'openclaw/cyrene'}]}),(503,{'ready':False,'failing':['agent-database:cyrene']})]):
            status,reason=gateway.gateway_status('test')
        self.assertEqual(status,'starting');self.assertIn('agent-database',reason)

    def test_foreign_token_is_conflict(self):
        with patch.object(gateway,'get_json',side_effect=[(200,{'ok':True,'status':'live'}),(401,{})]):
            self.assertEqual(gateway.gateway_status('test')[0],'conflict')

    def test_missing_listener(self):
        with patch.object(gateway,'get_json',return_value=(None,{})):
            self.assertEqual(gateway.gateway_status('test')[0],'absent')


class LockTests(unittest.TestCase):
    def test_lock_serializes_processes_and_old_file_is_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);lock=folder/'startup.lock';attempt=folder/'attempt';acquired=folder/'acquired'
            # A file surviving a reboot is harmless: ownership is an OS lock.
            lock.write_bytes(b'0')
            script = '''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from startup_lock import startup_lock
Path(sys.argv[3]).write_text('attempting')
with startup_lock(sys.argv[2],timeout=5):
    Path(sys.argv[4]).write_text('acquired')
'''
            process=None
            try:
                with startup_lock(lock):
                    process=subprocess.Popen([sys.executable,'-c',script,str(Path(__file__).parent),str(lock),str(attempt),str(acquired)],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    deadline=time.monotonic()+4
                    while not attempt.exists() and time.monotonic()<deadline:time.sleep(0.02)
                    self.assertTrue(attempt.exists())
                    time.sleep(0.15)
                    self.assertFalse(acquired.exists(),'second launcher entered before first released the lock')
                stdout,stderr=process.communicate(timeout=6)
                self.assertEqual(process.returncode,0,stderr.decode())
                self.assertTrue(acquired.exists())
                with startup_lock(lock,timeout=1): pass
            finally:
                if process and process.poll() is None:
                    process.terminate();process.wait(timeout=5)


if __name__=='__main__':unittest.main()
