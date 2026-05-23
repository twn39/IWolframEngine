import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock ipywidgets before importing kernel to keep unit tests self-contained and run-anywhere
mock_widgets = MagicMock()
sys.modules['ipywidgets'] = mock_widgets

# Mock IPython display publish_display_data
mock_display = MagicMock()
sys.modules['IPython.display'] = mock_display

from WolframLanguageForJupyter.kernel import WolframLanguageKernel

class TestWidgets(unittest.TestCase):
    def test_manipulate_interception_and_serialization(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        kernel = WolframLanguageKernel()
        
        # Mock VBox and DOMWidget model ID
        mock_box = MagicMock()
        mock_box.model_id = "test-model-id-12345"
        mock_widgets.VBox.return_value = mock_box
        
        responses = []
        kernel.send_response = MagicMock(side_effect=lambda socket, msg_type, content: responses.append((msg_type, content)))
        
        try:
            # Test 1: Integer range (should call IntSlider)
            code1 = 'Manipulate[Plot[Sin[a x], {x, 0, 10}], {a, 1, 5}]'
            res1 = loop.run_until_complete(kernel.do_execute(code1, silent=False))
            self.assertEqual(res1['status'], 'ok')
            mock_widgets.IntSlider.assert_called_once()
            
            # Extract arguments of IntSlider
            int_slider_args = mock_widgets.IntSlider.call_args[1]
            self.assertEqual(int_slider_args['min'], 1)
            self.assertEqual(int_slider_args['max'], 5)
            self.assertEqual(int_slider_args['description'], 'a')
            
            # Reset mock counts
            mock_widgets.IntSlider.reset_mock()
            mock_widgets.FloatSlider.reset_mock()
            
            # Test 2: Float range (should call FloatSlider)
            code2 = 'Manipulate[Plot[Sin[a x], {x, 0, 10}], {a, 1.0, 5.0}]'
            res2 = loop.run_until_complete(kernel.do_execute(code2, silent=False))
            self.assertEqual(res2['status'], 'ok')
            mock_widgets.FloatSlider.assert_called_once()
            
            # Extract arguments of FloatSlider
            float_slider_args = mock_widgets.FloatSlider.call_args[1]
            self.assertEqual(float_slider_args['min'], 1.0)
            self.assertEqual(float_slider_args['max'], 5.0)
            self.assertEqual(float_slider_args['description'], 'a')
            
            # Check published outputs
            data_list = [c['data'] for m, c in responses if m == 'execute_result']
            self.assertTrue(len(data_list) > 0)
            self.assertIn('application/vnd.jupyter.widget-view+json', data_list[0])
            self.assertEqual(data_list[0]['application/vnd.jupyter.widget-view+json']['model_id'], "test-model-id-12345")
            
            print("Widgets serialization, IntSlider and FloatSlider type mapping test PASSED!")
            
        finally:
            kernel.do_shutdown(restart=False)
            loop.close()

if __name__ == '__main__':
    unittest.main()
