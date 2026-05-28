import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestTimeMagic(unittest.TestCase):
    def test_time_magic(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            # 1. Test %time with basic expression
            res_time = loop.run_until_complete(kernel.do_execute("%time 1 + 2", silent=False))
            self.assertEqual(res_time['status'], 'ok')
            
            # Verify stdout prints the timing report
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("CPU times:" in msg for msg in stdout_msgs))
            self.assertTrue(any("Wall time:" in msg for msg in stdout_msgs))
            
            # Verify the result is still printed (it is the value 3)
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertIn("3", data_list[0]['text/plain'])
            
            # Reset responses
            responses.clear()
            
            # 2. Test %%time cell magic
            cell_code = "%%time\nPause[0.1];\n2 * 3"
            res_cell_time = loop.run_until_complete(kernel.do_execute(cell_code, silent=False))
            self.assertEqual(res_cell_time['status'], 'ok')
            
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("CPU times:" in msg for msg in stdout_msgs))
            self.assertTrue(any("Wall time:" in msg for msg in stdout_msgs))
            
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertIn("6", data_list[0]['text/plain'])
            
            # Reset responses
            responses.clear()
            
            # 3. Test %timeit with custom options
            res_timeit = loop.run_until_complete(kernel.do_execute("%timeit -n 5 -r 2 Pause[0.001]", silent=False))
            self.assertEqual(res_timeit['status'], 'ok')
            
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("per loop (mean" in msg for msg in stdout_msgs))
            self.assertTrue(any("2 runs" in msg for msg in stdout_msgs))
            self.assertTrue(any("5 loops" in msg for msg in stdout_msgs))
            
            # Reset responses
            responses.clear()
            
            # 4. Test %%timeit cell magic
            cell_timeit = "%%timeit -n 3 -r 2\nPause[0.001]\n4 + 4"
            res_cell_timeit = loop.run_until_complete(kernel.do_execute(cell_timeit, silent=False))
            self.assertEqual(res_cell_timeit['status'], 'ok')
            
            stdout_msgs = [c['text'] for m, c in responses if m == 'stream' and c['name'] == 'stdout']
            self.assertTrue(any("per loop (mean" in msg for msg in stdout_msgs))
            self.assertTrue(any("2 runs" in msg for msg in stdout_msgs))
            self.assertTrue(any("3 loops" in msg for msg in stdout_msgs))
            
            # Reset responses
            responses.clear()
            
            # 5. Test %timeit error handling (syntax error)
            res_err = loop.run_until_complete(kernel.do_execute("%timeit 1 + [2", silent=False))
            self.assertEqual(res_err['status'], 'error')
            self.assertEqual(res_err['ename'], 'SyntaxError')
            
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
