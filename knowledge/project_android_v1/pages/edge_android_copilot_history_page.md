# Copilot History Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_copilot_history_page",
  "name": "Copilot History Page",
  "identifiers": [
    {
      "name": "History row visible",
      "description": "The Copilot history page lists prior chat rows, with the first row observed as resourceId history_row_0."
    },
    {
      "name": "Prior chat title visible",
      "description": "A prior Samoyed chat was listed with visible text Samoyed Dog Information or Image."
    }
  ],
  "images": [],
  "elements": [
    {
      "name": "History item title",
      "role": "history entry text",
      "reference_locators": [
        {
          "strategy": "text",
          "selector": "Samoyed Dog Information or Image",
          "confidence": "medium",
          "notes": "Observed title for a prior chat created from the message Samoyed dog; use live title text for other prompts."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the expected prior Copilot chat appears in history."
          }
        }
      ]
    },
    {
      "name": "First history row",
      "role": "history entry",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "history_row_0",
          "confidence": "high",
          "notes": "Tapped successfully after verifying the visible Samoyed history title."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Reopens the selected prior conversation. Wait for the chat page to render before asserting prior user and response text."
          }
        }
      ]
    }
  ]
}
```