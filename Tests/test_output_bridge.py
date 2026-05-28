import unittest
import asyncio
import os
import sys
import time
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestOutputBridge(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.kernel = WolframLanguageKernel()
        self.responses = []
        self.kernel.send_response = MagicMock(
            side_effect=lambda socket, msg_type, content: self.responses.append((msg_type, content))
        )

    def tearDown(self):
        self.kernel.do_shutdown(restart=False)
        self.loop.close()

    def test_stdout_streaming(self):
        # Execute code that prints in a loop
        code = 'Do[Print["async-print-", i], {i, 1, 3}]'
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'ok')
        
        # Filter for stream stdout messages
        stdout_msgs = [c['text'] for m, c in self.responses if m == 'stream' and c['name'] == 'stdout']
        
        # Verify that all three print statements are captured
        self.assertIn("async-print-1\n", stdout_msgs)
        self.assertIn("async-print-2\n", stdout_msgs)
        self.assertIn("async-print-3\n", stdout_msgs)
        
        # Ensure there is no duplication (i.e. we only have exactly 3 stream prints)
        self.assertEqual(len(stdout_msgs), 3, f"Expected 3 prints, but got: {stdout_msgs}")

    def test_stderr_streaming(self):
        # Trigger a message/warning from Wolfram session
        code = 'Message[Symbol::argx, "test_func", 2]'
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'ok')
        
        # Filter for stream stderr messages
        stderr_msgs = [c['text'] for m, c in self.responses if m == 'stream' and c['name'] == 'stderr']
        
        self.assertTrue(len(stderr_msgs) > 0, "No stderr messages captured")
        # Check that it contains the message details
        self.assertTrue(any("Symbol::argx" in msg or "test_func" in msg for msg in stderr_msgs))
        
        # Ensure there is no duplication of stderr
        self.assertEqual(len(stderr_msgs), 1, f"Expected exactly 1 stderr message, but got: {stderr_msgs}")

    def test_jupyter_display(self):
        # Display an integer using JupyterDisplay
        code = 'JupyterDisplay[98765]'
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'ok')
        
        # Filter for display_data messages
        display_data_msgs = [c for m, c in self.responses if m == 'display_data']
        
        self.assertEqual(len(display_data_msgs), 1)
        self.assertEqual(display_data_msgs[0]['data']['text/plain'], '98765')

if __name__ == '__main__':
    unittest.main()
