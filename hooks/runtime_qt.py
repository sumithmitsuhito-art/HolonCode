"""Runtime hook: ensure PySide6 finds its bundled Qt plugins.

When a target machine has other Qt installations (e.g. from another
application or a system-wide Qt), environment variables like
QT_PLUGIN_PATH can point Qt to the wrong plugin directory, causing
platform plugin load failures and UI rendering fallback.

This hook runs before any other code in the frozen app and sanitises
the Qt environment so the bundled qt.conf takes priority.
"""
import os
import sys

if getattr(sys, 'frozen', False):
    for var in (
        'QT_PLUGIN_PATH',
        'QT_QPA_PLATFORM_PLUGIN_PATH',
        'QT_STYLE_OVERRIDE',
    ):
        os.environ.pop(var, None)
