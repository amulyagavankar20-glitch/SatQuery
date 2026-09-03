import unittest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from backend.agents.router import QwenRouter, QwenRouterError
from backend.schemas import RouteRequest, RouterTask

class TestQwenRouter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = QwenRouter()
        self.base_manifest = {"modality": "OPTICAL", "format": "GeoTIFF"}

    def _mock_response(self, mock_client_cls, response_json_str):
        # Setup the mock async client and its response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": response_json_str}
        
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        
        # httpx.AsyncClient works as an async context manager
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        return mock_client

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_vqa_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "SINGLE_VQA",
            "input_mode": "SINGLE_OPTICAL",
            "requires_grounding": false,
            "requires_change_analysis": false,
            "requires_optical_sar_analysis": false,
            "tools": ["geospatial_validator", "geochat_vqa"],
            "need_overlay": false,
            "params": {}
        }''')
        req = RouteRequest(query="What is in this image?", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.SINGLE_VQA)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_captioning_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "CAPTIONING",
            "input_mode": "SINGLE_OPTICAL",
            "requires_grounding": false,
            "requires_change_analysis": false,
            "requires_optical_sar_analysis": false,
            "tools": ["geospatial_validator", "geochat_describe"],
            "need_overlay": false,
            "params": {}
        }''')
        req = RouteRequest(query="Describe this image in detail.", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.CAPTIONING)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_grounding_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "GROUNDING",
            "input_mode": "SINGLE_OPTICAL",
            "requires_grounding": true,
            "requires_change_analysis": false,
            "requires_optical_sar_analysis": false,
            "tools": ["geospatial_validator", "mobilesam"],
            "need_overlay": true,
            "params": {}
        }''')
        req = RouteRequest(query="Find all ships.", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.GROUNDING)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_change_detection_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "CHANGE_DETECTION",
            "input_mode": "BI_TEMPORAL_OPTICAL",
            "requires_grounding": false,
            "requires_change_analysis": true,
            "requires_optical_sar_analysis": false,
            "tools": ["geospatial_validator", "bit_cd", "vectorizer"],
            "need_overlay": true,
            "params": {}
        }''')
        req = RouteRequest(query="Where has construction occurred between these two dates?", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.CHANGE_DETECTION)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_change_vqa_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "CHANGE_VQA",
            "input_mode": "BI_TEMPORAL_OPTICAL",
            "requires_grounding": false,
            "requires_change_analysis": true,
            "requires_optical_sar_analysis": false,
            "tools": ["geospatial_validator", "bit_cd", "geochat_describe"],
            "need_overlay": true,
            "params": {}
        }''')
        req = RouteRequest(query="What is the nature of the change in the highlighted region?", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.CHANGE_VQA)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_optical_sar_routing(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "OPTICAL_SAR_ANALYSIS",
            "input_mode": "OPTICAL_SAR",
            "requires_grounding": false,
            "requires_change_analysis": false,
            "requires_optical_sar_analysis": true,
            "tools": ["geospatial_validator", "fusion_s1s2"],
            "need_overlay": true,
            "params": {}
        }''')
        req = RouteRequest(query="Fuse optical and SAR to find vessels.", manifest=self.base_manifest)
        res = await self.router.route(req)
        self.assertEqual(res.task, RouterTask.OPTICAL_SAR_ANALYSIS)

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_contradictory_intent_flags_rejected(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "CHANGE_VQA",
            "input_mode": "BI_TEMPORAL_OPTICAL",
            "requires_grounding": false,
            "requires_change_analysis": false,
            "requires_optical_sar_analysis": false
        }''')
        req = RouteRequest(query="What changed?", manifest=self.base_manifest)
        with self.assertRaises(QwenRouterError) as context:
            await self.router.route(req)
        self.assertIn("Intent contradiction", str(context.exception))

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_unsupported_task(self, mock_client_cls):
        self._mock_response(mock_client_cls, '''{
            "task": "UNKNOWN_TASK_THAT_FAILS_VALIDATION",
            "input_mode": "SINGLE_OPTICAL",
            "tools": [],
            "need_overlay": false,
            "params": {}
        }''')
        req = RouteRequest(query="Do some weird unsupported thing", manifest=self.base_manifest)
        with self.assertRaises(QwenRouterError) as context:
            await self.router.route(req)
        self.assertIn("Router produced invalid structured output", str(context.exception))

    @patch('backend.agents.router.httpx.AsyncClient')
    async def test_malformed_router_output(self, mock_client_cls):
        self._mock_response(mock_client_cls, 'Oops this is not json { I failed ]')
        req = RouteRequest(query="Break the JSON", manifest=self.base_manifest)
        with self.assertRaises(QwenRouterError) as context:
            await self.router.route(req)
        self.assertIn("Router produced invalid structured output", str(context.exception))

if __name__ == '__main__':
    unittest.main()
