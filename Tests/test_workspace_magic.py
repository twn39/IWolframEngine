import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestWorkspaceMagic(unittest.TestCase):
    def test_workspace_and_clear_magic(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            # 1. Initially, the workspace should be empty or contain nothing we defined
            res_init = loop.run_until_complete(kernel.do_execute("%workspace", silent=False))
            self.assertEqual(res_init['status'], 'ok')
            
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertIn("Workspace is empty", data_list[0]['text/html'])
            
            # Reset responses
            responses.clear()
            
            # 2. Define some variables
            def_code = "workspaceVal = 500;\nworkspaceStr = \"hello world\";"
            res_def = loop.run_until_complete(kernel.do_execute(def_code, silent=False))
            self.assertEqual(res_def['status'], 'ok')
            
            # 3. Query %workspace
            res_work = loop.run_until_complete(kernel.do_execute("%workspace", silent=False))
            self.assertEqual(res_work['status'], 'ok')
            
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            html_report = data_list[-1]['text/html']
            self.assertIn("workspaceVal", html_report)
            self.assertIn("workspaceStr", html_report)
            self.assertIn("Integer", html_report)
            self.assertIn("String", html_report)
            self.assertIn("500", html_report)
            self.assertIn("hello world", html_report)
            
            # Reset responses
            responses.clear()
            
            # 4. Clear the variables
            res_clear = loop.run_until_complete(kernel.do_execute("%clear", silent=False))
            self.assertEqual(res_clear['status'], 'ok')
            
            # Check stdout streams from %clear
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("Cleared all variables" in msg for msg in stdout_msgs))
            
            # 5. Verify they are cleared
            responses.clear()
            res_check = loop.run_until_complete(kernel.do_execute("%workspace", silent=False))
            self.assertEqual(res_check['status'], 'ok')
            
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertIn("Workspace is empty", data_list[-1]['text/html'])
            
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
