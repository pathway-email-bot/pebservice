import unittest
from unittest.mock import MagicMock, patch
import json
import base64
import os
from dataclasses import dataclass

# 1. verify we can import the renamed module
from email_agent.scenario_models import Scenario
from email_agent.scenario_loader import load_scenario

@dataclass
class MockCloudEvent:
    data: dict

class TestCloudFunctionLogic(unittest.TestCase):
    
    def setUp(self):
        # Set dummy env vars to satisfy main.py checks
        self.env_patcher = patch.dict(os.environ, {
            "GMAIL_CLIENT_ID": "dummy_id",
            "GMAIL_CLIENT_SECRET": "dummy_secret",
            "GMAIL_REFRESH_TOKEN": "dummy_token",
            "OPENAI_API_KEY": "dummy_key"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_scenario_import_and_load(self):
        """Verify that we can import Scenario and load a default scenario."""
        # This confirms the rename fixed the collision issue logic
        s = load_scenario("email_agent/scenarios/missed_remote_standup.json")
        self.assertIsInstance(s, Scenario)
        self.assertEqual(s.name, "missed_remote_standup")

    @patch("main.get_gmail_service")
    @patch("main.EmailAgent") 
    def test_process_email_flow(self, mock_email_agent_cls, mock_get_gmail_service):
        """
        Simulate the entire Cloud Function flow with mocks.
        We mock:
        1. Gmail Service (API calls)
        2. EmailAgent (LLM calls)
        """
        # Import main inside test to ensure patches apply if main does import-time logic
        import main

        # MOCK SETUP
        mock_service = MagicMock()
        mock_get_gmail_service.return_value = mock_service

        # Mock EmailAgent instance and its method
        mock_agent_instance = mock_email_agent_cls.return_value
        mock_agent_instance.build_starter_thread.return_value = []
        
        # Mock result of evaluate_and_respond
        mock_grading_result = MagicMock()
        mock_grading_result.total_score = 5
        mock_grading_result.max_total_score = 5
        mock_grading_result.overall_comment = "Great job!"
        
        mock_eval_result = MagicMock()
        mock_eval_result.counterpart_reply = "Thanks for the update."
        mock_eval_result.grading = mock_grading_result
        
        mock_agent_instance.evaluate_and_respond.return_value = mock_eval_result

        # Mock Gmail History & Messages
        # history.list().execute()
        mock_service.users().history().list().execute.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg_123"}}
                    ]
                }
            ]
        }
        
        # messages.get().execute()
        # Return a fake email payload
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg_123",
            "threadId": "thread_abc",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "student@example.com"}
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": base64.urlsafe_b64encode(b"Hello manager").decode("utf-8")}
                    }
                ]
            }
        }

        # CONSTRUCT EVENT
        # A fake Pub/Sub message
        notification = {
            "emailAddress": "bot@example.com",
            "historyId": "100"
        }
        pubsub_data = json.dumps(notification)
        encoded_data = base64.b64encode(pubsub_data.encode("utf-8")).decode("utf-8")
        
        event = MockCloudEvent(data={"message": {"data": encoded_data}})

        # RUN FUNCTION
        res = main.process_email(event)

        # VERIFY
        self.assertEqual(res, "OK")
        
        # Verify Gmail service was called
        mock_service.users().history().list.assert_called()
        mock_service.users().messages().get.assert_called_with(userId='me', id='msg_123', format='full')
        
        # Verify Agent was called
        mock_email_agent_cls.assert_called() # Constructor
        mock_agent_instance.evaluate_and_respond.assert_called()
        
        # Verify Reply was sent
        mock_service.users().messages().send.assert_called()
        call_args = mock_service.users().messages().send.call_args
        # kwargs['body'] should contain the reply
        sent_body = call_args[1]['body']
        self.assertEqual(sent_body['threadId'], 'thread_abc')
        # Check that we didn't actually call OpenAI (implied by mocking EmailAgent)

if __name__ == '__main__':
    unittest.main()
