# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import os
import sublime
import sublime_plugin

import di


# DEBUG: before possibly reloading the di module, we need to clean it up
di.cleanup_module()
# DEBUG: use reimport to update all modules that have changed - this is needed
#        because Sublime Text will only reload modules in the plugin root
from third_party.reimport import reimport, modified
modified_modules = modified(os.path.relpath('di', os.getcwd()))
if len(modified_modules):
  print 'STDI: modules changed, reloading: %s' % (modified_modules)
  reimport(*modified_modules)


# class FooCommand(sublime_plugin.TextCommand):
#   def run(self, edit):
#     # self.view.window().show_quick_panel([
#     #   'a',
#     #   'b',
#     #   ],
#     #   self.callback)
#     #
#     #self.view.insert(edit, 0, "Hello, World!")
#     #
#     self.view.erase_regions('xx')
#     self.view.add_regions('xx', [self.view.line(0)], 'stdi.gutter.breakpoint', 'dot', sublime.HIDDEN)#sublime.DRAW_EMPTY_AS_OVERWRITE)#sublime.DRAW_OUTLINED)
#     self.view.set_status('xx', 'debugging')
#     pass

#   def callback(self, index):
#     print index


# Cached providers, mapped by provider URI
_providers = {}
# Active debuggers, mapped by instance URI
_debuggers = {}
# The debugger for each provider, mapped by provider URI
# TODO(benvanik): remove this - it limits things to one active session/provider
_debuggers_by_provider = {}


def _launch_debugger(target_window, provider_uri, attach):
  """Launches a debugger.

  Args:
    target_window: Target window.
    provider_uri: Provider URI.
    attach: True to attach to an existing instance.

  Returns:
    A Debugger, if it could be created and did not already exist.
  """
  global _providers
  global _debuggers
  global _debuggers_by_provider
  if provider_uri in _providers:
    provider = _providers.get(provider_uri)
  else:
    provider = di.create_provider(provider_uri)
    _providers[provider_uri] = provider

  if attach:
    print 'DEBUG: would attach'
  else:
    print 'DEBUG: would launch'

  # TODO(benvanik): async launch/pick instance from quickpanel, etc
  instance_info = provider.get_current_instances()[0]
  if instance_info.uri() in _debuggers:
    return None

  listener = DebuggerListener()
  debugger = instance_info.attach_debugger(listener)
  debugger.set_target_window(target_window)
  _debuggers[instance_info.uri()] = debugger
  _debuggers_by_provider[provider_uri] = debugger
  debugger.attach()

  global _status_manager
  _status_manager.show_message('Attaching debugger...')
  _status_manager.update()

  return debugger


def _get_debugger_provider_uri_for_view(view):
  """Gets the debugger provider URI for the given view.

  Args:
    view: View.

  Returns:
    A debugger provider URI, if one is defined.
  """
  settings = view.settings()
  return settings.get('stdi_provider', None)


def _get_debugger_for_view(view):
  """Gets the active debugger for the given view.

  Args:
    view: View.

  Returns:
    A Debugger, if one is attached.
  """
  global _debuggers_by_provider
  provider_uri = _get_debugger_provider_uri_for_view(view)
  return _debuggers_by_provider.get(provider_uri, None)


def _remove_debugger(debugger):
  """Removes a debugger from the active table.

  Args:
    debugger: Debugger instance.
  """
  global _debuggers
  global _debuggers_by_provider
  instance_uri = debugger.instance_info().uri()
  provider_uri = debugger.provider().uri()
  if not instance_uri in _debuggers:
    return
  del _debuggers[instance_uri]
  del _debuggers_by_provider[provider_uri]

  global _status_manager
  _status_manager.update()


def _callback_when_view_loaded(view, callback):
  """Waits until a view is loaded before calling the given callback.
  Since views are all loaded asynchronously, all operations on them must wait
  until they load. This will timeout-spin until the view is loaded.

  Args:
    view: View.
    callback: Callback.
  """
  if not view.is_loading():
    callback()
  else:
    sublime.set_timeout(lambda: _callback_when_view_loaded(view, callback), 1)


class StatusManager(object):
  """Status UI manager.
  Controls view and window status bars. Views should attach to the status
  manager to get relevant information.
  """
  def __init__(self, *args, **kwargs):
    pass

  def show_message(self, value):
    """Shows a temporary message in the status bar.

    Args:
      value: Message to show.
    """
    sublime.status_message(value)

  def show_error(self, value, ask_retry=False):
    """Shows an error message to the user.
    This is an annoying popup, so use sparingly.

    Args:
      value: Message to show.
      ask_retry: True to ask the user if they want to retry.

    Returns:
      True if the user chose to retry.
    """
    if ask_retry:
      return sublime.ok_cancel_dialog(value, 'Retry')
    else:
      sublime.error_message(value)
      return False

  def update(self):
    """Updates the active view, if any.
    """
    view = sublime.active_window().active_view()
    if view:
      self.update_view(view)

  def update_view(self, view):
    """Updates the status in the given view.

    Args:
      view: View.
    """
    debugger = _get_debugger_for_view(view)
    if not debugger:
      view.erase_status('stdi')
      return
    instance_info = debugger.instance_info()
    message = 'Debugging %s' % (instance_info.uri())
    view.set_status('stdi', message)


# Status manager
_status_manager = StatusManager()
def _show_status_message(value):
  """Shows a status message.

  Args:
    value: Message.
  """
  global _status_manager
  _status_manager.show_message(value)


class EventListener(sublime_plugin.EventListener):
  def on_post_save(self, view):
    global _debuggers
    # Notify all active debuggers that the given file has changed - they can
    # do what they want with that information
    uri = view.file_name()
    if not uri:
      return
    new_source = view.substr(sublime.Region(0, view.size()))
    for debugger in _debuggers.values():
      debugger.change_source(uri, new_source)

  def on_activated(self, view):
    global _status_manager
    _status_manager.update_view(view)

  def on_deactivated(self, view):
    global _status_manager
    _status_manager.update_view(view)


class DebuggerListener(di.EventListener):
  """Handles debugger events.
  """
  def __init__(self, *args, **kwargs):
    super(DebuggerListener, self).__init__(*args, **kwargs)
    self._active_location = None

  def on_attach(self, *args, **kwargs):
    print 'EVENT: on_attach'

  def on_detach(self, reason, *args, **kwargs):
    print 'EVENT: on_detach(%s)' % (reason)
    _remove_debugger(self.debugger())

    detach_message = 'Detached'
    if reason:
      detach_message += ': %s' % (reason)
    global _status_manager
    _status_manager.show_message(detach_message)
    # TODO(benvanik): don't show errors, they are annoying
    if reason:
      _status_manager.show_error(detach_message)

  def on_suspend(self, *args, **kwargs):
    print 'EVENT: on_suspend'

  def on_resume(self, *args, **kwargs):
    print 'EVENT: on_resume'

  def on_break(self, location, breakpoints_hit, snapshot, *args, **kwargs):
    print 'EVENT: on_break(%s@%s:%s)' % (location[0],
                                         location[1], location[2])
    self.set_active_location(location)

  def on_exception(self, location, is_uncaught, exception, snapshot,
                   *args, **kwargs):
    print 'EVENT: on_exception(%s@%s:%s)' % (location[0],
                                             location[1], location[2])
    self.set_active_location(location)

  def active_location(self):
    return self._active_location

  def set_active_location(self, location):
    self.clear_active_location()
    (uri, line, column) = location
    self._active_location = (uri, line, column)
    full_uri = '%s:%s:%s' % (uri, line + 1, column + 1)
    # TODO(benvanik): translate
    translated_path = full_uri
    window = self.debugger().target_window()
    view = window.open_file(translated_path, sublime.ENCODED_POSITION)
    _callback_when_view_loaded(view, self._foo)
  def _foo(self):
    print 'view opened and loaded'

  def clear_active_location(self):
    if self._active_location:
      pass
    self._active_location = None


class _WindowCommand(sublime_plugin.WindowCommand):
  """Global command, executed via command palette or key presses.
  """
  def get_debugger_provider_uri(self):
    """Gets the debugger provider URI for the current view.

    Returns:
      A debugger provider URI, if one is defined.
    """
    view = self.window.active_view()
    if not view:
      return None
    return _get_debugger_provider_uri_for_view(view)

  def has_debugger_configured(self):
    """Whether a debugger for the current view has been configured.

    Returns:
      True if a debugger has been configured.
    """
    if self.get_debugger():
      return True
    return not not self.get_debugger_provider_uri()

  def launch_debugger(self, attach=False):
    """Launches a debugger.

    Args:
      attach: Attach to an existing instance.

    Returns:
      A Debugger, if it could be created and did not already exist.
    """
    provider_uri = self.get_debugger_provider_uri()
    if not provider_uri:
      print 'STDI: no debug provider configured'
      return None
    return _launch_debugger(self.window, provider_uri, attach)

  def get_debugger(self):
    """Gets the active debugger for the active window/view.

    Returns:
      A Debugger, if one is attached.
    """
    view = self.window.active_view()
    if view:
      return _get_debugger_for_view(view)
    else:
      return None


class StdiToggleAllBreakpoints(_WindowCommand):
  """Enables/disables all breakpoints.
  """
  def run(self, action):
    print 'toggle all breakpoints: %s' % (action)


class StdiLaunchDebuggerCommand(_WindowCommand):
  """Launches a configured target app and attaches the debugger.
  """
  def run(self):
    debugger = self.launch_debugger()

  def is_enabled(self):
    return not self.get_debugger()

  def is_visible(self):
    return not self.get_debugger()


class StdiAttachDebuggerCommand(_WindowCommand):
  """Attaches to a configured target app if it is already running.
  """
  def run(self):
    debugger = self.launch_debugger(attach=True)

  def is_enabled(self):
    return not self.get_debugger()

  def is_visible(self):
    return not self.get_debugger()


class _ControlCommand(_WindowCommand):
  """Command that controls debugger flow.
  """
  def is_visible(self):
    return self.get_debugger()


class StdiDetachDebugger(_ControlCommand):
  """Detach debugger and leave running.
  """
  def run(self):
    _show_status_message('Detaching debugger...')
    debugger = self.get_debugger()
    debugger.detach(terminate=False)
    _remove_debugger(debugger)

  def is_enabled(self):
    return self.get_debugger()


class StdiStopDebugger(_ControlCommand):
  """Detach debugger and terminate.
  """
  def run(self):
    _show_status_message('Stopping debugger...')
    debugger = self.get_debugger()
    debugger.detach(terminate=True)
    _remove_debugger(debugger)

  def is_enabled(self):
    return self.get_debugger()


class StdiDebugPauseCommand(_ControlCommand):
  """Debugger control: pause/continue.
  """
  def run(self):
    debugger = self.get_debugger()
    if debugger.is_running():
      _show_status_message('Pausing...')
      debugger.suspend()
    else:
      _show_status_message('Resuming...')
      debugger.resume()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and (debugger.can_suspend() or
                         debugger.can_resume())


class StdiDebugStepOverCommand(_ControlCommand):
  """Debugger control: step over.
  """
  def run(self):
    _show_status_message('Stepping over...')
    debugger = self.get_debugger()
    debugger.step_over()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_step_over()


class StdiDebugStepInCommand(_ControlCommand):
  """Debugger control: step in.
  """
  def run(self):
    _show_status_message('Stepping in...')
    debugger = self.get_debugger()
    debugger.step_in()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_step_in()


class StdiDebugStepOutCommand(_ControlCommand):
  """Debugger control: step out.
  """
  def run(self):
    _show_status_message('Stepping out...')
    debugger = self.get_debugger()
    debugger.step_out()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_step_out()


class StdiEvaluate(_WindowCommand):
  """Evaluate an expression in the current context.
  """
  def run(self):
    debugger = self.get_debugger()
    # TODO(benvanik): show an input panel, ask for expression
    #_show_status_message('Evaluating expression...')
    #debugger.evaluate()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_evaluate()

  def is_visible(self):
    return self.get_debugger()


class _ContextCommand(_WindowCommand):
  """Context menu command.
  """
  def get_line_number(self):
    """Gets the line number currently selected in the active view.

    Returns:
      A line number in the active view, or None if no view is active.
    """
    return None


class StdiContinueToHereCommand(_ContextCommand):
  """Continues until the clicked line is executed.
  If no debugger is attached this will attempt to attach one.
  """
  def run(self):
    debugger = self.get_debugger()
    if debugger:
      print 'continue to here'
    else:
      print 'launch and continue to here'
      debugger = self.launch_debugger()
      #debugger.continue_to(...)

  def is_visible(self):
    if not super(StdiContinueToHereCommand, self).is_visible():
      return False
    return self.has_debugger_configured()

  def description(self):
    if self.get_debugger():
      return 'Continue to Here'
    else:
      return 'Launch and Continue to Here'


class _BreakpointContextCommand(_ContextCommand):
  """Context menu command that relates to breakpoints.
  """
  def get_line_breakpoint(self):
    """Get the breakpoint on the currently clicked line.

    Returns:
      A Breakpoint on the clicked line, if one exists.
    """
    line_number = self.get_line_number()
    if line_number is None:
      return None
    return None


class StdiAddBreakpointCommand(_BreakpointContextCommand):
  """Adds a new breakpoint on the clicked line.
  """
  def run(self):
    bp = self.get_line_breakpoint()
    if bp:
      return
    print 'add bp'

  def is_visible(self):
    if not super(StdiAddBreakpointCommand, self).is_visible():
      return False
    return self.get_debugger() and not self.get_line_breakpoint()


class StdiToggleBreakpointCommand(_BreakpointContextCommand):
  """Enables or disables the breakpoint on the clicked line.
  """
  def run(self):
    bp = self.get_line_breakpoint()
    if not bp:
      return
    print 'toggle bp'

  def is_visible(self):
    if not super(StdiToggleBreakpointCommand, self).is_visible():
      return False
    return self.get_line_breakpoint()

  def description(self):
    bp = self.get_line_breakpoint()
    # if not bp.is_enabled():
    #   return 'Enable Breakpoint'
    # else:
    #   return 'Disable Breakpoint'
    return '{Enable} Breakpoint'


class StdiEditBreakpointCommand(_BreakpointContextCommand):
  """Edits the breakpoint on the clicked line.
  """
  def run(self):
    bp = self.get_line_breakpoint()
    if not bp:
      return
    print 'edit bp'

  def is_visible(self):
    if not super(StdiEditBreakpointCommand, self).is_visible():
      return False
    return self.get_line_breakpoint()


class StdiRemoveBreakpointCommand(_BreakpointContextCommand):
  """Removes an existing breakpoint from the clicked line.
  """
  def run(self):
    bp = self.get_line_breakpoint()
    if not bp:
      return
    print 'remove bp'

  def is_visible(self):
    if not super(StdiRemoveBreakpointCommand, self).is_visible():
      return False
    return self.get_line_breakpoint()
