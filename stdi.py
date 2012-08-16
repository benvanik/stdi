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


# TODO(benvanik): move to SourceView
def _get_syntax_name(view):
  """Gets the name of the syntax used in the given view.

  Args:
    view: View.

  Returns:
    The name of the syntax used in the given view.
  """
  syntax = view.settings().get('syntax')
  return os.path.splitext(os.path.basename(syntax))[0]


class DebugPlugin(object):
  """
  """
  def __init__(self, *args, **kwargs):
    # Cached providers, mapped by provider URI
    self._providers = {}
    # Active debuggers, mapped by instance URI
    self._debuggers = {}
    # The debugger for each provider, mapped by provider URI
    # TODO(benvanik): remove this - it limits things to one active session
    self._debuggers_by_provider = {}

    # Breakpoint list
    breakpoint_file = os.path.join(sublime.packages_path(),
                                   '..',
                                   'Settings',
                                   'Breakpoints.sublime_session')
    self._breakpoint_listener = BreakpointListener(self)
    self._breakpoint_list = di.load_breakpoint_list(breakpoint_file,
                                                    self._breakpoint_listener)

    # Status manager
    self._status_manager = StatusManager(self)

    # All source views that exist, by view.id()
    self._source_views = {}

    # Scan all open views to build source views
    # TODO(benvanik): find a way to prevent this
    for window in sublime.windows():
      for view in window.views():
        self.get_source_view(view)

  def debuggers(self):
    return self._debuggers.values()

  def breakpoint_list(self):
    return self._breakpoint_list

  def status_manager(self):
    return self._status_manager

  def show_status_message(self, value):
    """Shows a status message.

    Args:
      value: Message.
    """
    self._status_manager.show_message(value)

  def _get_provider_for_uri(self, uri):
    """Gets a debugging provider for a URI.
    Creates or returns a cached provider.

    Args:
      uri: URI to get the provider for.

    Returns:
      An InstanceProvider, if one was found.
    """
    if uri in self._providers:
      provider = self._providers.get(uri)
    else:
      provider = di.create_provider(uri)
      self._providers[uri] = provider
    return provider

  def launch_debugger(self, target_window, provider_uri, attach, callback=None):
    """Launches a debugger.

    Args:
      target_window: Target window.
      provider_uri: Provider URI.
      attach: True to attach to an existing instance.
      callback: Callback that will receive the Debugger or None if it failed or
                already existed.
    """
    provider = self._get_provider_for_uri(provider_uri)
    if not provider:
      print 'STDI: no provider found for URI %s' % (provider_uri)
      self.show_status_message('No provider found for URI %s' % (provider_uri))
      sublime.set_timeout(lambda: callback(None))
      return

    if attach:
      print 'DEBUG: would attach'
    else:
      print 'DEBUG: would launch'

    # Query instances async
    def _queried_instances(instance_infos):
      if not len(instance_infos):
        print 'STDI: no instances found on provider'
        self.show_status_message('No debuggable instances found!')
        callback(None)
      if not provider.is_single_instance():
        # Need to show a list
        items = []
        for instance_info in instance_infos:
          items.append([
              instance_info.display_name(),
              instance_info.display_info(),
              ])
        def _item_selected(index):
          if index == -1:
            callback(None)
            return
          instance_info = instance_infos[index]
          self._attach_to_instance(target_window, instance_info)
        target_window.show_quick_panel(
            items, _item_selected, sublime.MONOSPACE_FONT)
      else:
        # Pick the only one we have
        self._attach_to_instance(target_window, instance_infos[0])
    provider.query_instances(_queried_instances)

  def _attach_to_instance(self, target_window, instance_info):
    """Attaches to an instance.

    Args:
      target_window: Target window.
      instance_info: Instance to attach to.
    """
    # Ensure not running
    if instance_info.uri() in self._debuggers:
      return None

    # Create
    provider = instance_info.provider()
    listener = DebuggerListener(self)
    debugger = instance_info.attach_debugger(listener)
    debugger.set_target_window(target_window)
    self._debuggers[instance_info.uri()] = debugger
    self._debuggers_by_provider[provider.uri()] = debugger
    debugger.attach()

    self._status_manager.show_message('Attaching debugger...')
    self._status_manager.update()

    return debugger

  def get_debugger_provider_uri_for_view(self, view):
    """Gets the debugger provider URI for the given view.

    Args:
      view: View.

    Returns:
      A debugger provider URI, if one is defined.
    """
    settings = view.settings()
    return settings.get('debug_target', None)

  def get_debugger_for_view(self, view):
    """Gets the active debugger for the given view.

    Args:
      view: View.

    Returns:
      A Debugger, if one is attached.
    """
    provider_uri = self.get_debugger_provider_uri_for_view(view)
    return self._debuggers_by_provider.get(provider_uri, None)

  def remove_debugger(self, debugger):
    """Removes a debugger from the active table.

    Args:
      debugger: Debugger instance.
    """
    instance_uri = debugger.instance_info().uri()
    provider_uri = debugger.provider().uri()
    if not instance_uri in self._debuggers:
      return
    del self._debuggers[instance_uri]
    del self._debuggers_by_provider[provider_uri]
    self._status_manager.update()

  def get_source_view(self, view, create=True):
    """Gets a SourceView for the given ST view.

    Args:
      view: ST view.
      create: True to create if needed.

    Returns:
      A SourceView, created on demand if needed.
    """
    source_view = self._source_views.get(view.id(), None)
    if not source_view and create:
      source_view = SourceView(self, view)
      self._source_views[view.id()] = source_view
    return source_view

  def cleanup_source_view(self, view):
    """Removes a SourceView for the given ST view.

    Args:
      view: ST view.
    """
    source_view = self._source_views.get(view.id(), None)
    if source_view:
      source_view.cleanup()
      del self._source_views[view.id()]

  def active_location(self):
    return self._active_location

  def set_active_location(self, debugger, location):
    """Sets the active location, opening views and changing focus.

    Args:
      debugger: Debugger that is requesting the location change.
      location: (uri, line, column) location.
    """
    if not location:
      self.clear_active_location()
      return
    (uri, line, column) = location
    self._active_location = (uri, line, column)
    # TODO(benvanik): translate uri (source map/etc)
    translated_path = uri
    full_path = '%s:%s:%s' % (translated_path, line + 1, column + 1)
    window = debugger.target_window()
    new_view = window.open_file(full_path, sublime.ENCODED_POSITION |
                                           0)#sublime.TRANSIENT)
    new_view = self.get_source_view(new_view)
    if not new_view.is_loading():
      window.focus_view(new_view.view())

    # Enumerate all views we know about and update them
    # TODO(benvanik): faster - lookup by filename
    for source_view in self._source_views.values():
      if source_view.file_name() == translated_path:
        source_view.set_active_location(location)
      else:
        source_view.clear_active_location()

  def clear_active_location(self):
    """Clears the active location.
    """
    if not self._active_location:
      return
    (uri, line, column) = self._active_location
    # TODO(benvanik): translate uri (source map/etc)
    translated_path = uri
    for source_view in self._source_views.values():
      if source_view.file_name() == translated_path:
        source_view.clear_active_location()
    self._active_location = None


class StatusManager(object):
  """Status UI manager.
  Controls view and window status bars. Views should attach to the status
  manager to get relevant information.
  """
  def __init__(self, plugin, *args, **kwargs):
    """Initializes the status manager.

    Args:
      plugin: Parent plugin.
    """
    self._plugin = plugin

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
    debugger = self._plugin.get_debugger_for_view(view)
    if not debugger:
      view.erase_status('stdi')
      return
    instance_info = debugger.instance_info()
    message = 'Debugging %s' % (instance_info.uri())
    view.set_status('stdi', message)


class SourceView(object):
  """A ST view wrapper that manages a single views overlays and state.
  A DebugPlugin will manage these views, creating and deleting them as required,
  to enable sensible control over the custom regions/etc added to a normal ST
  view.

  This type uses metaprogramming to make it act like an ST view (mostly).
  """
  def __init__(self, plugin, view, *args, **kwargs):
    """Initializes a source view.

    Args:
      plugin: Parent plugin.
      view: ST view.
    """
    self._plugin = plugin
    self._view = view
    self._active_location = None

  def __getattr__(self, name):
    if hasattr(self._view, name):
      return getattr(self._view, name)
    raise AttributeError('Attribute %s not found' % (name))

  def view(self):
    return self._view

  def cleanup(self):
    """Called before the view is disposed to cleanup all changes.
    """
    # TODO(benvanik): remove everything!
    pass

  def on_load(self):
    """Called once the view has loaded.
    """
    self.set_active_location(self._active_location)
    if self._active_location:
      self.window().focus_view(self._view)

  def active_location(self):
    return self._active_location

  def set_active_location(self, location):
    self.clear_active_location()
    if not location:
      return
    (uri, line, column) = location
    self._active_location = (uri, line, column)

    point = self.text_point(line, column)
    region = self.line(point)

    # Pick based on breakpoint/exception/etc
    scope = 'stdi.gutter.active_line'
    icon = 'bookmark '

    self.add_regions('stdi_view_active',
                     [region],
                     scope,
                     icon,
                     sublime.DRAW_EMPTY)
    self.show(point)

  def clear_active_location(self):
    if not self._active_location:
      return
    self.erase_regions('stdi_view_active')
    self._active_location = None


class EventListener(sublime_plugin.EventListener):
  def on_new(self, view):
    plugin().get_source_view(view)

  def on_clone(self, view):
    plugin().get_source_view(view)

  def on_load(self, view):
    source_view = plugin().get_source_view(view, create=True)
    if source_view:
      source_view.on_load()

  def on_close(self, view):
    plugin().cleanup_source_view(view)

  def on_post_save(self, view):
    # Notify all active debuggers that the given file has changed - they can
    # do what they want with that information
    uri = view.file_name()
    if not uri:
      return
    new_source = view.substr(sublime.Region(0, view.size()))
    for debugger in plugin().debuggers():
      debugger.change_source(uri, new_source)

  def on_activated(self, view):
    plugin().status_manager().update_view(view)

  def on_deactivated(self, view):
    plugin().status_manager().update_view(view)


class BreakpointListener(di.BreakpointListener):
  """Handles breakpoint list events.
  """
  def __init__(self, plugin, *args, **kwargs):
    super(BreakpointListener, self).__init__(*args, **kwargs)
    self._plugin = plugin

  def on_breakpoint_add(self, breakpoint):
    print 'EVENT: on_breakpoint_add'
    for debugger in plugin().debuggers():
      debugger.add_breakpoint(breakpoint)

  def on_breakpoint_change(self, breakpoint):
    print 'EVENT: on_breakpoint_change'
    for debugger in plugin().debuggers():
      debugger.change_breakpoint(breakpoint)

  def on_breakpoint_remove(self, breakpoint):
    print 'EVENT: on_breakpoint_remove'
    for debugger in plugin().debuggers():
      debugger.remove_breakpoint(breakpoint)


class DebuggerListener(di.DebuggerListener):
  """Handles debugger events.
  """
  def __init__(self, plugin, *args, **kwargs):
    super(DebuggerListener, self).__init__(*args, **kwargs)
    self._plugin = plugin

  def on_attach(self, *args, **kwargs):
    print 'EVENT: on_attach'
    # Add all breakpoints
    debugger = self.debugger()
    breakpoint_list = plugin().breakpoint_list()
    for breakpoint in breakpoint_list.breakpoints():
      debugger.add_breakpoint(breakpoint)

  def on_detach(self, reason, *args, **kwargs):
    print 'EVENT: on_detach(%s)' % (reason)
    plugin().remove_debugger(self.debugger())
    plugin().clear_active_location()

    status_manager = self._plugin.status_manager()
    detach_message = 'Detached'
    if reason:
      detach_message += ': %s' % (reason)
    status_manager.show_message(detach_message)
    # TODO(benvanik): don't show errors, they are annoying
    if reason:
      status_manager.show_error(detach_message)

  def on_suspend(self, *args, **kwargs):
    print 'EVENT: on_suspend'

  def on_resume(self, *args, **kwargs):
    print 'EVENT: on_resume'
    plugin().clear_active_location()

  def on_break(self, location, breakpoints_hit, snapshot, *args, **kwargs):
    print 'EVENT: on_break(%s@%s:%s)' % (location[0],
                                         location[1] + 1, location[2] + 1)
    if len(breakpoints_hit):
      print '  breakpoints hit: %s' % (breakpoints_hit)
    plugin().set_active_location(self.debugger(), location)

  def on_exception(self, location, is_uncaught, exception, snapshot,
                   *args, **kwargs):
    print 'EVENT: on_exception(%s@%s:%s)' % (location[0],
                                             location[1] + 1, location[2] + 1)
    plugin().set_active_location(self.debugger(), location)


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
    return plugin().get_debugger_provider_uri_for_view(view)

  def has_debugger_configured(self):
    """Whether a debugger for the current view has been configured.

    Returns:
      True if a debugger has been configured.
    """
    if self.get_debugger():
      return True
    return not not self.get_debugger_provider_uri()

  def launch_debugger(self, attach=False, callback=None):
    """Launches a debugger.

    Args:
      attach: Attach to an existing instance.
      callback: Callback to call with the Debugger or none if it could not be
                created, already existed, or the action was cancelled.
    """
    def _dummy(debugger):
      pass
    callback = callback or _dummy
    provider_uri = self.get_debugger_provider_uri()
    if not provider_uri:
      print 'STDI: no debug provider configured'
      plugin().show_status_message('No debug provider configured')
      sublime.set_timeout(lambda: callback(None), 0)
      return

    # Launch!
    plugin().launch_debugger(self.window, provider_uri, attach, callback)

  def get_debugger(self):
    """Gets the active debugger for the active window/view.

    Returns:
      A Debugger, if one is attached.
    """
    view = self.window.active_view()
    if view:
      return plugin().get_debugger_for_view(view)
    else:
      return None

  def get_view_uri(self):
    """Gets the URI of the current view, if any.

    Returns:
      A URI or None if there is no view or the file has not yet been named.
    """
    view = self.window.active_view()
    if view:
      return view.file_name()
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
    self.launch_debugger()

  def is_enabled(self):
    return not self.get_debugger()

  def is_visible(self):
    return not self.get_debugger()


class StdiAttachDetachDebuggerCommand(_WindowCommand):
  """Attaches or detach to a configured target app if it is already running.
  """
  def run(self):
    if not self.get_debugger():
      self.launch_debugger(attach=True)
    else:
      plugin().show_status_message('Detaching debugger...')
      debugger = self.get_debugger()
      debugger.detach(terminate=False)
      plugin().remove_debugger(debugger)

  def description(self):
    if not self.get_debugger():
      return 'Attach Debugger'
    else:
      return 'Detach Debugger'


class _ControlCommand(_WindowCommand):
  """Command that controls debugger flow.
  """
  def is_visible(self):
    return self.get_debugger()


class StdiStopDebugger(_ControlCommand):
  """Detach debugger and terminate.
  """
  def run(self):
    plugin().show_status_message('Stopping debugger...')
    debugger = self.get_debugger()
    debugger.detach(terminate=True)
    plugin().remove_debugger(debugger)

  def is_enabled(self):
    return self.get_debugger()


class StdiDebugPauseCommand(_ControlCommand):
  """Debugger control: pause/continue.
  """
  def run(self):
    debugger = self.get_debugger()
    if debugger.is_running():
      plugin().show_status_message('Pausing...')
      debugger.suspend()
    else:
      plugin().show_status_message('Resuming...')
      debugger.resume()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and (debugger.can_suspend() or
                         debugger.can_resume())


class StdiDebugStepOverCommand(_ControlCommand):
  """Debugger control: step over.
  """
  def run(self):
    plugin().show_status_message('Stepping over...')
    debugger = self.get_debugger()
    debugger.step_over()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_step_over()


class StdiDebugStepInCommand(_ControlCommand):
  """Debugger control: step in.
  """
  def run(self):
    plugin().show_status_message('Stepping in...')
    debugger = self.get_debugger()
    debugger.step_in()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_step_in()


class StdiDebugStepOutCommand(_ControlCommand):
  """Debugger control: step out.
  """
  def run(self):
    plugin().show_status_message('Stepping out...')
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
    #plugin().show_status_message('Evaluating expression...')
    #debugger.evaluate()

  def is_enabled(self):
    debugger = self.get_debugger()
    return debugger and debugger.can_evaluate()

  def is_visible(self):
    return self.get_debugger()


class _ContextCommand(_WindowCommand):
  """Context menu command.
  """
  # TODO(benvanik): could make this get_locations to enable actions with
  #                 multiple selection, but I don't use that so I don't care!
  def get_location(self, include_column=False):
    """Gets the cursor location of the current view.

    Args:
      include_column: True to include the column number, otherwise it will be
                      0 to indicate the entire line.

    Returns:
      A (uri, line, column) location or None if no selection.
    """
    view = self.window.active_view()
    if not view or not len(view.sel()):
      return None
    sel = view.sel()[0]
    (line, column) = view.rowcol(sel.a)
    if not include_column:
      column = 0
    return (self.get_view_uri(), line, column)


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
      self.launch_debugger()
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
    location = self.get_location()
    if not location:
      return
    breakpoint_list = plugin().breakpoint_list()
    return breakpoint_list.get_breakpoint_at_location(location)


class StdiAddRemoveBreakpointCommand(_BreakpointContextCommand):
  """Adds a new breakpoint on the clicked line.
  """
  def run(self):
    location = self.get_location()
    if not location:
      return
    breakpoint_list = plugin().breakpoint_list()
    breakpoint = breakpoint_list.get_breakpoint_at_location(location)
    if not breakpoint:
      breakpoint_list.create_breakpoint_at_location(location)
      plugin().show_status_message(
          'Added breakpoint at line %s' % (location[1] + 1))
    else:
      breakpoint_list.remove_breakpoint(breakpoint)
      plugin().show_status_message(
          'Removed breakpoint at line %s' % (location[1] + 1))

  def description(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint:
      return 'Add Breakpoint'
    else:
      return 'Remove Breakpoint'


class StdiToggleBreakpointCommand(_BreakpointContextCommand):
  """Enables or disables the breakpoint on the clicked line.
  """
  def run(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint:
      return
    breakpoint.set_enabled(not breakpoint.is_enabled())

  def is_visible(self):
    if not super(StdiToggleBreakpointCommand, self).is_visible():
      return False
    return self.get_line_breakpoint()

  def description(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint:
      return 'None'
    if not breakpoint.is_enabled():
      return 'Enable Breakpoint'
    else:
      return 'Disable Breakpoint'


class StdiEditBreakpointConditionCommand(_BreakpointContextCommand):
  """Edits the breakpoint condition on the clicked line.
  """
  def run(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint:
      return
    def _on_done(new_value):
      new_value = new_value.strip()
      if not len(new_value):
        new_value = None
      breakpoint.set_condition(new_value)
    input_view = self.window.show_input_panel(
        'New Condition:',
        breakpoint.condition() or '',
        _on_done, None, None)
    input_view.run_command('select_all')

  def is_visible(self):
    if not super(StdiEditBreakpointConditionCommand, self).is_visible():
      return False
    return self.get_line_breakpoint()

  def description(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint or not breakpoint.condition():
      return 'Edit Condition...'
    else:
      return 'Condition: \'%s\'...' % (breakpoint.condition())


class StdiIgnoreBreakpointCommand(_BreakpointContextCommand):
  """Edits the breakpoint ignore count on the clicked line.
  """
  def run(self):
    breakpoint = self.get_line_breakpoint()
    if not breakpoint:
      return
    def _on_done(new_value):
      try:
        new_value = int(new_value)
      except:
        return
      for debugger in plugin().debuggers():
        debugger.ignore_breakpoint(breakpoint, new_value)
    input_view = self.window.show_input_panel(
        'Ignore Hits:',
        '1',
        _on_done, None, None)
    input_view.run_command('select_all')

  def is_visible(self):
    if not super(StdiIgnoreBreakpointCommand, self).is_visible():
      return False
    if not len(plugin().debuggers()):
      return False
    return self.get_line_breakpoint()


class StdiPositionedContextMenuCommand(sublime_plugin.TextCommand):
  """Very hacky way of moving selection when the user right clicks.
  This enables us to right-click -> add breakpoint at the point where the
  user actually clicked, instead of wherever their selection happened to be.
  """
  def run_(self, args):
    self.view.run_command("drag_select", {'event': args['event']})
    # new_sel = self.view.sel()
    # click_point = new_sel[0].a
    # (line, column) = self.view.rowcol(click_point)
    # print '%s:%s (%s)' % (line + 1, column + 1, click_point)
    self.view.run_command('context_menu', args)


# Global plugin
_plugin = DebugPlugin()
def plugin():
  global _plugin
  return _plugin
