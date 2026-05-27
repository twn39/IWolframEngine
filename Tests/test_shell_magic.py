import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestShellMagic(unittest.TestCase):
    def test_cell_magic(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            code = "%%sh\necho 'Hello from cell magic'\necho 'Line 2'"
            res = loop.run_until_complete(kernel.do_execute(code, silent=False))
            
            self.assertEqual(res['status'], 'ok')
            
            # Check stdout streams
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            full_stdout = "".join(stdout_msgs)
            self.assertIn("Hello from cell magic", full_stdout)
            self.assertIn("Line 2", full_stdout)
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

    def test_line_magic_mixed(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            code = "mixedVal = 100;\n%sh echo 'Interleaved shell output'\nmixedVal + 50"
            res = loop.run_until_complete(kernel.do_execute(code, silent=False))
            
            self.assertEqual(res['status'], 'ok')
            
            # Check stdout streams from %sh
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            full_stdout = "".join(stdout_msgs)
            self.assertIn("Interleaved shell output", full_stdout)
            
            # Check final evaluate result (should be 150)
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertEqual(data_list[0]['text/plain'], '150')
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

    def test_empty_magic(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            code = "%sh \n1 + 1"
            res = loop.run_until_complete(kernel.do_execute(code, silent=False))
            
            self.assertEqual(res['status'], 'ok')
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertEqual(data_list[0]['text/plain'], '2')
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

    def test_shell_error_propagation(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            # First segment defines x = 200, second fails, third should not run
            code = "x = 200;\n%sh false\nx = 300;"
            res = loop.run_until_complete(kernel.do_execute(code, silent=False))
            
            # The execution should return error because shell command failed (exit code 1)
            self.assertEqual(res['status'], 'error')
            self.assertEqual(res['ename'], 'ShellError')
            
            # Verify x is still 200 (x = 300 should not have been executed)
            check_res = loop.run_until_complete(kernel.do_execute("x", silent=False))
            self.assertEqual(check_res['status'], 'ok')
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertEqual(data_list[-1]['text/plain'], '200')
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
