import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestStdin(unittest.TestCase):
    def test_input_string(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        kernel.raw_input = MagicMock(return_value="Wolfram User")
        
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            code = 'InputString["What is your name?"]'
            res = loop.run_until_complete(kernel.do_execute(code, silent=False, allow_stdin=True))
            
            self.assertEqual(res['status'], 'ok')
            kernel.raw_input.assert_called_once_with("What is your name?")
            
            # Check published outputs
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertEqual(data_list[0]['text/plain'], '"Wolfram User"')
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

    def test_input_expression(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        # Feed math expression string "2 + 3"
        kernel.raw_input = MagicMock(return_value="2 + 3")
        
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            code = 'Input["Enter a math expression:"]'
            res = loop.run_until_complete(kernel.do_execute(code, silent=False, allow_stdin=True))
            
            self.assertEqual(res['status'], 'ok')
            kernel.raw_input.assert_called_once_with("Enter a math expression:")
            
            # Check published outputs (the evaluated result of "2 + 3" should be 5)
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertEqual(data_list[0]['text/plain'], '5')
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
