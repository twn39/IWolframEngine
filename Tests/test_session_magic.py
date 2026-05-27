import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestSessionMagic(unittest.TestCase):
    def test_session_info_and_restart(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            # 1. Query %session info
            res_info = loop.run_until_complete(kernel.do_execute("%session info", silent=False))
            self.assertEqual(res_info['status'], 'ok')
            
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            html_report = data_list[0]['text/html']
            text_report = data_list[0]['text/plain']
            
            # Verify the HTML structure and variables are present
            self.assertIn("Wolfram Engine Session Information", html_report)
            self.assertIn("Process ID (PID)", html_report)
            self.assertIn("Memory Usage", html_report)
            self.assertIn("Executable Path", html_report)
            
            # Store initial PID
            pid_line = [line for line in text_report.splitlines() if "Process ID (PID):" in line]
            self.assertTrue(len(pid_line) > 0)
            initial_pid = pid_line[0].split(":", 1)[1].strip()
            self.assertNotEqual(initial_pid, "Unknown")
            
            # 2. Define a test variable to verify it is cleared on restart
            res_def = loop.run_until_complete(kernel.do_execute("sessionTestVal = 999;", silent=False))
            self.assertEqual(res_def['status'], 'ok')
            
            # Reset responses
            responses.clear()
            
            # 3. Query %session restart
            res_restart = loop.run_until_complete(kernel.do_execute("%session restart", silent=False))
            self.assertEqual(res_restart['status'], 'ok')
            
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("session restarted successfully" in msg.lower() for msg in stdout_msgs))
            
            # Reset responses
            responses.clear()
            
            # 4. Check %session info again to verify PID has changed
            res_info_after = loop.run_until_complete(kernel.do_execute("%session info", silent=False))
            self.assertEqual(res_info_after['status'], 'ok')
            
            data_list_after = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list_after) > 0)
            text_report_after = data_list_after[0]['text/plain']
            
            pid_line_after = [line for line in text_report_after.splitlines() if "Process ID (PID):" in line]
            self.assertTrue(len(pid_line_after) > 0)
            after_pid = pid_line_after[0].split(":", 1)[1].strip()
            self.assertNotEqual(after_pid, "Unknown")
            self.assertNotEqual(initial_pid, after_pid)
            
            # 5. Check if variable sessionTestVal is now cleared/undefined
            responses.clear()
            
            # Let's query %workspace to see if it is empty
            res_workspace = loop.run_until_complete(kernel.do_execute("%workspace", silent=False))
            self.assertEqual(res_workspace['status'], 'ok')
            
            data_list_ws = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list_ws) > 0)
            self.assertIn("Workspace is empty", data_list_ws[-1]['text/html'])
            
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
