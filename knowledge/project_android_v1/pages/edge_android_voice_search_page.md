# Voice Search Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_voice_search_page",
  "name": "Voice Search Page",
  "identifiers": [
    {
      "name": "Voice prompt visible",
      "description": "The voice page shows text such as Speak now in English after the NTP or focused-omnibox mic is tapped."
    },
    {
      "name": "Voice wave visible",
      "description": "The voice page exposes com.microsoft.emmx:id/voice_wave; this is the structural marker for the blue wave voice UI. Use assert_with_ai when the requirement specifically asks to verify the wave color."
    },
    {
      "name": "Voice close visible",
      "description": "The voice page exposes com.microsoft.emmx:id/voice_close for returning to the New Tab Page or prior Edge surface."
    }
  ],
  "images": [],
  "elements": [
    {
      "name": "Voice prompt",
      "role": "text",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/voice_message",
          "confidence": "high",
          "notes": "Observed with text Speak now in English after tapping the voice search mic."
        },
        {
          "strategy": "text",
          "selector": "Speak now in English",
          "confidence": "medium",
          "notes": "Locale-dependent prompt text; prefer the resource id when available."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the voice search page opened."
          }
        }
      ]
    },
    {
      "name": "Voice wave",
      "role": "visual indicator",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/voice_wave",
          "confidence": "high",
          "notes": "Structural marker for the visible voice wave area. For blue-wave color verification, keep this page open and use assert_with_ai."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the voice wave UI is present."
          }
        },
        {
          "operation": "assert_with_ai",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Use when the requirement specifically asks for a blue wave rather than just the voice_wave element."
          }
        }
      ]
    },
    {
      "name": "Close voice button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/voice_close",
          "confidence": "high",
          "notes": "Closes the voice page."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Closes voice search and returns to the New Tab Page or prior Edge surface. Verify the NTP marker after closing when the case requires return to NTP."
          }
        }
      ]
    }
  ]
}
```