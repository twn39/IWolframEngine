import unittest
import asyncio
import os
import sys
import re
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class TestDiagnostics(unittest.TestCase):
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

    def test_trailing_operator(self):
        # Invalid code with trailing plus operator
        code = "1 + "
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['ename'], 'SyntaxError')
        self.assertEqual(res['evalue'], 'Syntax error: Expected an operand.')
        
        # Verify the published error event
        error_events = [c for m, c in self.responses if m == 'error']
        self.assertEqual(len(error_events), 1)
        
        tb = error_events[0]['traceback']
        pointer_line = [strip_ansi(line) for line in tb if '^' in strip_ansi(line)]
        self.assertTrue(len(pointer_line) > 0)
        # Indent: 4 spaces + (col 5 - 1) = 8 spaces
        self.assertTrue(pointer_line[0].startswith("        ^"))
        self.assertIn("ExpectedOperand", pointer_line[0])

    def test_missing_bracket_closer(self):
        # Invalid code with unclosed bracket
        code = "f[a"
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['ename'], 'SyntaxError')
        self.assertEqual(res['evalue'], 'Syntax error: Missing closer.')
        
        error_events = [c for m, c in self.responses if m == 'error']
        self.assertEqual(len(error_events), 1)
        
        tb = error_events[0]['traceback']
        pointer_line = [strip_ansi(line) for line in tb if '^' in strip_ansi(line)]
        self.assertTrue(len(pointer_line) > 0)
        # Indent: 4 spaces + (col 2 - 1) = 5 spaces
        self.assertTrue(pointer_line[0].startswith("     ^"))
        self.assertIn("GroupMissingCloser", pointer_line[0])

    def test_extra_comma(self):
        # f[a, , b] is syntactically valid in Wolfram (evaluates to f[a, Null, b] with a warning)
        code = "f[a, , b]"
        res = self.loop.run_until_complete(self.kernel.do_execute(code, silent=False))
        
        self.assertEqual(res['status'], 'ok')
        
        # Verify execution result evaluates to f[a, Null, b]
        exec_results = [c['data'] for m, c in self.responses if m == 'execute_result']
        self.assertEqual(len(exec_results), 1)
        self.assertEqual(exec_results[0]['text/plain'], 'f[a, Null, b]')

if __name__ == '__main__':
    unittest.main()
