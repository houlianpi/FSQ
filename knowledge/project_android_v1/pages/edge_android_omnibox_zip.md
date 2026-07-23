# Omnibox ZIP Suggestions

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_omnibox_zip",
  "name": "Omnibox ZIP Suggestions",
  "identifiers": [
    {"name": "Top sites list visible", "description": "Opening the NTP search box shows the ZIP/top-sites suggestion list."},
    {"name": "Camera and microphone actions visible", "description": "The focused omnibox state exposes attachment camera search and mic buttons. If the unfocused NTP already shows edge_ntp_mic_button, voice can start directly from the NTP without first focusing the URL bar."},
    {"name": "URL bar focused", "description": "The editable URL bar receives typed keywords and URLs."}
  ],
  "images": [
    {"path": "../assets/images/screenshot_1778750987134.png", "description": "Search/omnibox state with bottom toolbar mode."}
  ],
  "elements": [
    {
      "name": "URL bar",
      "role": "text field",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/url_bar", "confidence": "high", "notes": "Primary URL and keyword input locator across search, refresh, search-engine, and suggestion flows."}
      ],
      "operations": [
        {"operation": "input_text", "result": {"type": "state_change", "to_page_id": "edge_android_omnibox_zip", "description": "Typing text keeps focus in omnibox and can reveal the suggestion dropdown."}},
        {"operation": "press_key_enter", "result": {"type": "navigate", "to_page_id": "edge_android_web_page", "description": "Submitting a URL or keyword loads a web page or search results page."}}
      ]
    },
    {
      "name": "Top sites list",
      "role": "list",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/suggestion_top_sites_list", "confidence": "high", "notes": "Verified immediately after tapping the NTP search box."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the omnibox/ZIP suggestions page is open."}}
      ]
    },
    {
      "name": "Suggestion dropdown",
      "role": "list",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/omnibox_suggestions_dropdown", "confidence": "high", "notes": "Verified after entering text into the omnibox."},
        {"strategy": "xpath", "selector": "//androidx.recyclerview.widget.RecyclerView[@resource-id='com.microsoft.emmx:id/omnibox_suggestions_dropdown']/android.view.ViewGroup[1]", "confidence": "medium", "notes": "First URL suggestion used for developer.wikimedia.org."}
      ],
      "operations": [
        {"operation": "tap_first_suggestion", "result": {"type": "navigate", "to_page_id": "edge_android_web_page", "description": "Selects a suggestion and loads the selected page or result."}}
      ]
    },
    {
      "name": "Camera search button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/attachment_right_camera_button", "confidence": "high", "notes": "Verified as an omnibox marker in top and bottom mode."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the camera search action is available."}}
      ]
    },
    {
      "name": "Copilot voice button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/attachment_right_mic_button", "confidence": "high", "notes": "Focused-omnibox mic button. Use only after the URL bar has been focused; for direct NTP voice, prefer edge_ntp_mic_button on the New Tab Page."},
        {"strategy": "accessibility id", "selector": "Start voice search", "confidence": "medium", "notes": "Shared accessibility label with the direct NTP mic."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the focused-omnibox voice action is available."}},
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_voice_search_page", "description": "Starts voice from the focused omnibox state."}}
      ]
    },
    {
      "name": "Search history keyword",
      "role": "suggestion item",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@resource-id='com.microsoft.emmx:id/line_1' and @text='microsoft']", "confidence": "medium", "notes": "Search suggestion hint after searching microsoft, opening a new tab, and focusing the search box."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms a previous keyword is visible in ZIP search history."}}
      ]
    }
  ]
}
```