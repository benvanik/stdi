# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import sublime
import sublime_plugin


class CustomView(object):
  """A ST view that is used for debugger IO.
  """
  def __init__(self, window, debugger, title, *args, **kwargs):
    """Initializes a custom view.

    Args:
      window: Target sublime window.
      debugger: Debugger.
      title: View title.
    """
    self._window = window
    self._debugger = debugger
    active_view = window.active_view()
    self._view = window.new_file()
    window.focus_view(active_view)
    self._view.set_name(title)
    self._view.set_read_only(True)
    self._view.set_scratch(True)
    #self._view.set_syntax_file('Packages/Python/Python.tmLanguage')
    settings = self._view.settings()
    settings.set('stdi_callstack', True)
    settings.set('command_mode', False)
    settings.set('line_numbers', False)
    settings.set('caret_style', 'blink')
    settings.set('auto_complete', False)
    settings.set('draw_white_space', 'none')
    settings.set('word_wrap', False)
    settings.set('gutter', True)
    settings.set('spell_check', False)
    settings.set('rulers', [])
    #settings.set('color_scheme', os.path.join(PACKAGE_DIR, 'stdi.tmTheme'))

  def window(self):
    return self._window

  def debugger(self):
    return self._debugger

  def view(self):
    return self._view

  def focus(self):
    self._window.focus_view(self._view)

  def close(self):
    active_view = self._window.active_view()
    self._window.focus_view(self._view)
    self._window.run_command('close')
    self._window.focus_view(active_view)


class TreeView(CustomView):
  """A ST view displaying a navigable.
  """
  def __init__(self, window, debugger, title, *args, **kwargs):
    """Initializes a tree view.

    Args:
      window: Target sublime window.
      debugger: Debugger.
      title: View title.
    """
    super(TreeView, self).__init__(window, debugger, title, *args, **kwargs)
