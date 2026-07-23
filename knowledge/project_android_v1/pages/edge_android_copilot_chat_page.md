# Copilot Chat Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_copilot_chat_page",
  "name": "Copilot Chat Page",
  "identifiers": [
    {
      "name": "Message input visible",
      "description": "The Copilot chat page exposes an android.widget.EditText or the placeholder text Message Copilot or @ mention a tab."
    },
    {
      "name": "Empty chat greeting visible",
      "description": "A fresh Copilot chat can show the greeting text Hi there, good to see you."
    },
    {
      "name": "Close control visible",
      "description": "The Copilot page exposes a Close accessibility action that returns to the New Tab Page."
    }
  ],
  "images": [],
  "elements": [
    {
      "name": "Message input",
      "role": "text field",
      "reference_locators": [
        {
          "strategy": "class name",
          "selector": "android.widget.EditText",
          "confidence": "high",
          "notes": "Used successfully for tapping and inputText after the Copilot page opened."
        },
        {
          "strategy": "text",
          "selector": "Message Copilot or @ mention a tab",
          "confidence": "medium",
          "notes": "Placeholder visible in fresh/new chat state; can be used to tap the input before text entry."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Focuses the Copilot message input."
          }
        },
        {
          "operation": "input_text",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Enters a Copilot prompt such as Hello, copilot! or Samoyed dog."
          }
        }
      ]
    },
    {
      "name": "Send button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "Send",
          "confidence": "high",
          "notes": "Submits the current Copilot message after inputText succeeds."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Sends the message; wait for response generation before asserting response text."
          }
        }
      ]
    },
    {
      "name": "Copilot response text",
      "role": "message",
      "reference_locators": [
        {
          "strategy": "text",
          "selector": "response text returned by Copilot",
          "confidence": "medium",
          "notes": "Use live response text for assertions; successful runs verified greetings and Samoyed-related response content."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms Copilot responded after the message was sent."
          }
        }
      ]
    },
    {
      "name": "New chat button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "New chat",
          "confidence": "high",
          "notes": "Clears the current visible chat and opens a fresh Copilot chat state."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Starts a fresh chat. The prior exact message should not be visible; empty greeting and input placeholder should be visible."
          }
        }
      ]
    },
    {
      "name": "Chat history navigation button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "Navigate to chat history",
          "confidence": "high",
          "notes": "Top-left Copilot control used after starting a new chat to open Copilot history."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_copilot_history_page",
            "description": "Opens the Copilot history page."
          }
        }
      ]
    },
    {
      "name": "Close button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "Close",
          "confidence": "high",
          "notes": "Closes Copilot and returns to the New Tab Page."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Returns to NTP. Confirm url_bar text contains Search or ask anything and Close is not visible."
          }
        }
      ]
    },
    {
      "name": "Retained conversation content",
      "role": "message list",
      "reference_locators": [
        {
          "strategy": "text",
          "selector": "prior user message or prior Copilot response text",
          "confidence": "medium",
          "notes": "After closing and reopening Copilot, retained content may require scrolling before exact text is visible."
        }
      ],
      "operations": [
        {
          "operation": "swipe_then_verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Verifies conversation retention after reopening Copilot from NTP."
          }
        }
      ]
    }
  ]
}
```