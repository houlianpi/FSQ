# Overflow Menu

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_overflow_menu",
  "name": "Overflow Menu",
  "identifiers": [
    {
      "name": "Menu entries visible",
      "description": "The overflow menu exposes text entries such as Downloads, Favorites, History, Settings, New InPrivate Tab, Exit browser, and All menu."
    },
    {
      "name": "Opened from NTP browser menu",
      "description": "This page opens by tapping the bottom overflow button on the NTP or a returned NTP state."
    },
    {
      "name": "Signed-in account descriptor visible",
      "description": "A signed-in MSA menu can expose com.microsoft.emmx:id/menu_active_account_desc with text Personal."
    }
  ],
  "images": [
    {
      "path": "../assets/images/screenshot_1778749768612.png",
      "description": "Overflow menu after tapping the browser menu."
    }
  ],
  "elements": [
    {
      "name": "Personal account type",
      "role": "account descriptor",
      "reference_locators": [
        {
          "strategy": "id + text",
          "selector": "com.microsoft.emmx:id/menu_active_account_desc text=Personal",
          "confidence": "high",
          "notes": "Verified in a signed-in MSA flow after opening Browser menu from NTP."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the overflow menu is open and the active account is personal."
          }
        },
        {
          "operation": "press_key_back",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Dismisses the overflow menu; the NTP container should be visible and this descriptor should no longer be visible."
          }
        }
      ]
    },
    {
      "name": "Downloads",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Downloads']",
          "confidence": "high",
          "notes": "Primary text locator for the Downloads menu item."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_downloads_panel",
            "description": "Opens the Downloads hub panel."
          }
        }
      ]
    },
    {
      "name": "Favorites",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Favorites']",
          "confidence": "high",
          "notes": "Primary text locator for the Favorites menu item."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_favorites_panel",
            "description": "Opens the Favorites hub panel."
          }
        }
      ]
    },
    {
      "name": "History",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='History']",
          "confidence": "high",
          "notes": "Primary text locator for the History menu item."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_history_panel",
            "description": "Opens the History hub panel."
          }
        }
      ]
    },
    {
      "name": "Settings",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Settings']",
          "confidence": "high",
          "notes": "Primary text locator for Settings access and settings-related flows."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_settings_page",
            "description": "Opens the Settings page."
          }
        }
      ]
    },
    {
      "name": "New InPrivate Tab",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='New InPrivate Tab']",
          "confidence": "high",
          "notes": "Primary text locator for opening an InPrivate tab."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_inprivate_page",
            "description": "Opens a New InPrivate tab."
          }
        }
      ]
    },
    {
      "name": "Exit browser",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Exit browser']",
          "confidence": "medium",
          "notes": "Requires a horizontal menu-page swipe before selection when not visible on the current menu page."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "open_dialog",
            "to_page_id": "edge_android_exit_confirmation_dialog",
            "description": "Opens the Exit Microsoft Edge confirmation dialog."
          }
        }
      ]
    },
    {
      "name": "All menu",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='All menu']",
          "confidence": "low",
          "notes": "Low-confidence hint; do not rely on this path unless live UI confirms it."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": null,
            "description": "May open an All Menu panel. Treat this as unconfirmed until live UI verifies the transition."
          }
        }
      ]
    }
  ]
}
```