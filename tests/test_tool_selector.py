import unittest
from unittest.mock import MagicMock
from backend.models import ToolRegistry
from backend.schemas import RouterTask, InputClass
from backend.agents.tool_selector import ToolSelector, ToolSelectorError

class TestToolSelector(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.selector = ToolSelector(self.db)
        
        # Tools are enabled and support CHANGE_DETECTION and BI_TEMPORAL by default
        def create_mock_tool(tool_id):
            tool = ToolRegistry(tool_id=tool_id, name=tool_id, enabled=True)
            tool.supported_tasks = ["CHANGE_DETECTION"]
            tool.supported_modalities = ["BI_TEMPORAL"]
            return tool
            
        self.mock_tools = {
            "preprocess": create_mock_tool("preprocess"),
            "align": create_mock_tool("align"),
            "bit_cd": create_mock_tool("bit_cd"),
            "vectorize": create_mock_tool("vectorize")
        }

    def _mock_db_result(self, tool_ids):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        # Return only the tools that are both in the sequence AND in our fake DB
        mock_scalars.all.return_value = [self.mock_tools[tid] for tid in tool_ids if tid in self.mock_tools]
        mock_result.scalars.return_value = mock_scalars
        self.db.execute.return_value = mock_result

    def test_correct_tool_sequence(self):
        seq = self.selector.get_tool_sequence(RouterTask.CHANGE_DETECTION)
        self.assertEqual(seq, ["preprocess", "align", "bit_cd", "vectorize"])

    def test_valid_selection(self):
        self._mock_db_result(["preprocess", "align", "bit_cd", "vectorize"])
        seq = self.selector.validate_selection(RouterTask.CHANGE_DETECTION, InputClass.BI_TEMPORAL)
        self.assertEqual(seq, ["preprocess", "align", "bit_cd", "vectorize"])

    def test_unknown_tool(self):
        # We need "preprocess" and "geochat_vqa" for CAPTIONING
        # "geochat_vqa" is not in self.mock_tools
        self.mock_tools["preprocess"].supported_tasks.append(RouterTask.CAPTIONING.value)
        self.mock_tools["preprocess"].supported_modalities.append(InputClass.SINGLE_OPTICAL.value)
        self._mock_db_result(["preprocess", "geochat_vqa"])
        with self.assertRaises(ToolSelectorError) as context:
            self.selector.validate_selection(RouterTask.CAPTIONING, InputClass.SINGLE_OPTICAL)
        self.assertIn("Unknown tool:", str(context.exception))

    def test_disabled_tool(self):
        self.mock_tools["bit_cd"].enabled = False
        self._mock_db_result(["preprocess", "align", "bit_cd", "vectorize"])
        
        with self.assertRaises(ToolSelectorError) as context:
            self.selector.validate_selection(RouterTask.CHANGE_DETECTION, InputClass.BI_TEMPORAL)
        self.assertIn("Disabled tool:", str(context.exception))

    def test_incompatible_tool(self):
        # Tool doesn't support CHANGE_DETECTION
        self.mock_tools["bit_cd"].supported_tasks = ["SOME_OTHER_TASK"]
        self._mock_db_result(["preprocess", "align", "bit_cd", "vectorize"])
        
        with self.assertRaises(ToolSelectorError) as context:
            self.selector.validate_selection(RouterTask.CHANGE_DETECTION, InputClass.BI_TEMPORAL)
        self.assertIn("Incompatible tool:", str(context.exception))

    def test_wrong_input_class(self):
        # bit_cd only supports BI_TEMPORAL
        self._mock_db_result(["preprocess", "align", "bit_cd", "vectorize"])
        with self.assertRaises(ToolSelectorError) as context:
            self.selector.validate_selection(RouterTask.CHANGE_DETECTION, InputClass.SINGLE_OPTICAL)
        self.assertIn("Wrong input class:", str(context.exception))

if __name__ == '__main__':
    unittest.main()
