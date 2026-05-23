import unittest
import asyncio
import os
import sys
import signal
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestInterrupt(unittest.TestCase):
    def test_execution_interruption(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        kernel.old_sigint_handler = MagicMock()
        
        # Verify initial states
        self.assertFalse(kernel._executing)
        self.assertFalse(kernel._interrupted)
        
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        # Schedule the SIGINT call after 1 second of execution
        async def trigger_interrupt():
            await asyncio.sleep(1)
            print("Simulating SIGINT signal...")
            # We call handle_sigint directly. In a real environment, the OS sends SIGINT
            # which python forwards to the registered handler.
            kernel.handle_sigint(signal.SIGINT, None)
            
        try:
            # We run a Pause[10] calculation, and concurrently run the trigger_interrupt task
            code = 'Pause[10]'
            
            async def run_test():
                task1 = asyncio.create_task(kernel.do_execute(code, silent=False))
                task2 = asyncio.create_task(trigger_interrupt())
                res, _ = await asyncio.gather(task1, task2)
                return res
            
            res = loop.run_until_complete(run_test())
            
            # Check execution status and response
            self.assertEqual(res['status'], 'error')
            self.assertEqual(res['ename'], 'KeyboardInterrupt')
            self.assertIn('interrupted', res['evalue'].lower())
            
            # Check published outputs to iopub
            err_responses = [c for m, c in responses if m == 'error']
            self.assertTrue(len(err_responses) > 0)
            self.assertEqual(err_responses[0]['ename'], 'KeyboardInterrupt')
            self.assertIn('interrupted', err_responses[0]['evalue'].lower())
            
            print("Verification of interruption PASSED!")
            
            # Now verify that subsequent evaluations work without restarting!
            print("Running subsequent evaluation '2 + 3' to verify self-healing...")
            res2 = loop.run_until_complete(kernel.do_execute('2 + 3', silent=False))
            self.assertEqual(res2['status'], 'ok')
            
            # Verify the result of 2 + 3 is 5
            exec_results = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(exec_results) > 0)
            self.assertEqual(exec_results[-1]['text/plain'], '5')
            
            print("Self-healing and subsequent execution PASSED!")
            
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
