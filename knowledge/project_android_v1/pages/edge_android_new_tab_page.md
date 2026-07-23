# New Tab Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_new_tab_page",
  "name": "New Tab Page",
  "identifiers": [
    {
      "name": "Account menu visible",
      "description": "The New Tab Page exposes an Account menu entry, a stable NTP readiness marker."
    },
    {
      "name": "NTP container visible",
      "description": "The New Tab Page container resource com.microsoft.emmx:id/edge_ntp_swipe_refresh_layout is a deterministic readiness and return marker."
    },
    {
      "name": "NTP scroll view visible",
      "description": "The main New Tab Page container is visible after returning from hub panels or dialogs."
    },
    {
      "name": "Search box visible",
      "description": "The NTP search box/address entry is available for search and URL entry flows."
    },
    {
      "name": "Direct NTP voice search button visible",
      "description": "The New Tab Page can expose com.microsoft.emmx:id/edge_ntp_mic_button with Start voice search, which starts voice directly without first focusing the URL bar."
    },
    {
      "name": "Copilot entry visible",
      "description": "The NTP location bar exposes a Copilot button for opening the Copilot chat page."
    }
  ],
  "images": [
    {
      "path": "../assets/images/screenshot_1778749755004.png",
      "description": "NTP state before opening the overflow menu."
    },
    {
      "path": "../assets/images/screenshot_1778749824996.png",
      "description": "NTP state after returning from the Downloads panel with Android Back."
    }
  ],
  "elements": [
    {
      "name": "Account menu",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "Account menu",
          "confidence": "high",
          "notes": "Common NTP readiness marker."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the browser is on or has returned to the New Tab Page."
          }
        },
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_account_rewards_panel",
            "description": "Opens the account area; a signed-in account can expose Microsoft Rewards."
          }
        }
      ]
    },
    {
      "name": "Browser menu",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/overflow_button_bottom",
          "confidence": "high",
          "notes": "Bottom toolbar overflow button opens the browser menu from NTP and returned NTP states."
        },
        {
          "strategy": "accessibility id",
          "selector": "Browser menu",
          "confidence": "high",
          "notes": "Observed together with the overflow_button_bottom resource id in the signed-in MSA flow."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_overflow_menu",
            "description": "Opens the browser overflow menu from the bottom toolbar."
          }
        }
      ]
    },
    {
      "name": "Copilot button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/edge_location_bar_copilot_button",
          "confidence": "high",
          "notes": "Stable NTP entry point used by chat, close, retention, new-chat, and history flows."
        },
        {
          "strategy": "accessibility id",
          "selector": "Copilot",
          "confidence": "medium",
          "notes": "Available in some NTP states; prefer the resource id when present."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_copilot_chat_page",
            "description": "Opens the Copilot chat page from the New Tab Page."
          }
        }
      ]
    },
    {
      "name": "Search box",
      "role": "text field entry point",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/search_box_text",
          "confidence": "high",
          "notes": "Search box entry for entering URL or keyword text from NTP."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_omnibox_zip",
            "description": "Focuses the omnibox and opens the ZIP suggestions page."
          }
        }
      ]
    },
    {
      "name": "Direct voice search button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/edge_ntp_mic_button",
          "confidence": "high",
          "notes": "Visible on the unfocused NTP search bar; use this directly for voice-search cases when the mic is already visible."
        },
        {
          "strategy": "accessibility id",
          "selector": "Start voice search",
          "confidence": "medium",
          "notes": "Shared accessibility label with the focused omnibox mic; pair with the NTP mic resource id when possible."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_voice_search_page",
            "description": "Starts the non-Copilot voice search page directly from the New Tab Page. Do not focus the URL bar first unless the case explicitly requires the focused omnibox state or the direct NTP mic is absent."
          }
        },
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms voice search can be started directly from the New Tab Page."
          }
        }
      ]
    },
    {
      "name": "Tab center button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/tab_center_button",
          "confidence": "high",
          "notes": "Used to enter tab center before clearing tabs and closing a tab thumbnail."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_tab_center",
            "description": "Opens the tab center."
          }
        }
      ]
    },
    {
      "name": "Add new tab button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/edge_bottom_bar_plus_button",
          "confidence": "high",
          "notes": "Tab counter available after loading pages and returning to toolbar state."
        },
        {
          "strategy": "accessibility id",
          "selector": "Add New tab",
          "confidence": "medium",
          "notes": "Observed when creating a fresh NTP before opening Copilot."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Creates a new tab and opens a fresh New Tab Page."
          }
        }
      ]
    },
    {
      "name": "New Tab Page container",
      "role": "container",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/edge_ntp_swipe_refresh_layout",
          "confidence": "high",
          "notes": "Passed post-Back assertions after dismissing the overflow menu."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the New Tab Page is visible after launch, Back dismissal, or returning from panels."
          }
        }
      ]
    },
    {
      "name": "URL bar on NTP",
      "role": "text field entry point",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/url_bar",
          "confidence": "medium",
          "notes": "After closing Copilot, this element was enabled/clickable and contained Search or ask anything."
        }
      ],
      "operations": [
        {
          "operation": "verify_state",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms Copilot is closed and the NTP search/address bar is available."
          }
        }
      ]
    }
  ]
}
```