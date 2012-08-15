# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import json
import os
import sublime


class BreakpointListener(object):
  """Breakpoint list event listener.
  Receives breakpoint event notifications.
  """
  def __init__(self, *args, **kwargs):
    self._breakpoint_list = None

  def breakpoint_list(self):
    return self._breakpoint_list

  def on_breakpoint_add(self, breakpoint):
    """Handles breakpoint additions.

    Args:
      breakpoint: Breakpoint that was added.
    """
    pass

  def on_breakpoint_change(self, breakpoint):
    """Handles breakpoint changes.

    Args:
      breakpoint: Breakpoint that changed.
    """
    pass

  def on_breakpoint_remove(self, breakpoint):
    """Handles breakpoint removals.

    Args:
      breakpoint: Breakpoint that was removed.
    """
    pass


class BreakpointList(object):
  """A serializable list of breakpoints.
  Breakpoints are retained across debugging sessions in this type, and by
  ensuring all breakpoint management flows through this list it's possible to
  have consistent UI preserved across sessions.
  """
  def __init__(self, debuggers, listener, *args, **kwargs):
    """Initializes a breakpoint list.

    Args:
      debuggers: A mutable list of debuggers.
      listener: BreakpointListener to receive events.
    """
    self._debuggers = debuggers
    self._listener = listener
    self._listener._breakpoint_list = self
    self._is_dirty = True
    self._save_pending = False
    self._path = None
    self._next_id = 0
    self._breakpoints = {}
    self._breakpoints_by_location = {}
    self._breakpoints_by_function = {}

  def _get_next_id(self):
    """Gets the next ID that can be used for a breakpoint.

    Returns:
      A string breakpoint ID.
    """
    while True:
      next_id = str(self._next_id)
      self._next_id += 1
      if not next_id in self._breakpoints:
        break
    return next_id

  def load(self, path):
    """Loads the breakpoint list.

    Args:
      path: Path to load from.
    """
    self._is_dirty = False
    self._path = path
    try:
      with open(self._path, 'r') as f:
        blob = json.loads(f.read())
    except:
      blob = {}
    breakpoint_objs = blob.get('breakpoints', [])
    for breakpoint_obj in breakpoint_objs:
      breakpoint = Breakpoint(
          self,
          breakpoint_obj['id'],
          location=breakpoint_obj.get('location', None),
          function_name=breakpoint_obj.get('function_name', None))
      self._breakpoints[breakpoint.id()] = breakpoint
      if breakpoint.type() == 'location':
        self._breakpoints_by_location[breakpoint.location()] = breakpoint
      elif breakpoint.type() == 'function':
        self._breakpoints_by_function[breakpoint.function_name()] = breakpoint
      breakpoint.set_display_name(breakpoint_obj['display_name'])
      breakpoint.set_enabled(breakpoint_obj['is_enabled'])
      breakpoint.set_condition(breakpoint_obj['condition'])
      breakpoint.set_ignore_count(breakpoint_obj['ignore_count'])

  def save(self, path=None):
    """Saves the breakpoint list.

    Args:
      path: A new path to save to. Omit to use the past last loaded from.
    """
    self._save_pending = False
    if not path and not self._path:
      print 'STDI: no path specified for save'
      return
    if path:
      self._path = path
    if not self._is_dirty:
      return
    self._is_dirty = False
    breakpoint_objs = []
    for breakpoint in self._breakpoints.values():
      breakpoint_obj = {
          'id': breakpoint.id(),
          'display_name': breakpoint.display_name(),
          'is_enabled': breakpoint.is_enabled(),
          'condition': breakpoint.condition(),
          'ignore_count': breakpoint.ignore_count(),
          }
      if breakpoint.type() == 'location':
        breakpoint_obj['location'] = breakpoint.location()
      elif breakpoint.type() == 'function':
        breakpoint_obj['function_name'] = breakpoint.function_name()
      breakpoint_objs.append(breakpoint_obj)

    with open(self._path, 'w') as f:
      f.write(json.dumps({
          'breakpoints': breakpoint_objs,
          }))

  def _add_breakpoint(self, breakpoint):
    """Adds a breakpoint.
    The breakpoint must already be initialized.

    Args:
      breakpoint: Breakpoint to add.
    """
    self._breakpoints[breakpoint.id()] = breakpoint
    if breakpoint.type() == 'location':
      self._breakpoints_by_location[breakpoint.location()] = breakpoint
    elif breakpoint.type() == 'function':
      self._breakpoints_by_function[breakpoint.function_name()] = breakpoint
    self._invalidate()
    self._listener.on_breakpoint_add(breakpoint)

  def create_breakpoint_at_location(self, location):
    """Creates a new breakpoint for a location.

    Args:
      location: (uri, line, column) location.

    Returns:
      A new Breakpoint or None if one already exists.
    """
    breakpoint = self.get_breakpoint_at_location(location)
    if breakpoint:
      return None
    breakpoint = Breakpoint(self, self._get_next_id(), location=location)
    self._add_breakpoint(breakpoint)
    return breakpoint

  def get_breakpoint_at_location(self, location):
    """Gets a breakpoint at the given location.

    Args:
      location: (uri, line, column) location.

    Returns:
      The Breakpoint at the given location, if one exists.
    """
    return self._breakpoints_by_location.get(location, None)

  def create_breakpoint_for_function(self, function_name):
    """Creates a new breakpoint for a function call.

    Args:
      function_name: Function name.

    Returns:
      A new Breakpoint or None if one already exists.
    """
    breakpoint = self.get_breakpoint_for_function(function_name)
    if breakpoint:
      return None
    breakpoint = Breakpoint(self, self._get_next_id(),
                            function_name=function_name)
    self._add_breakpoint(breakpoint)
    return breakpoint

  def get_breakpoint_for_function(self, function_name):
    """Gets a breakpoint at the given function.

    Args:
      function_name: Function name.

    Returns:
      The Breakpoint for the given function, if one exists.
    """
    return self._breakpoints_by_function.get(function_name, None)

  def remove_breakpoint(self, breakpoint):
    """Removes the given breakpoint.

    Args:
      breakpoint: Breakpoint.
    """
    if not breakpoint.id() in self._breakpoints:
      return
    if breakpoint.type() == 'location':
      del self._breakpoints_by_location[breakpoint.location()]
    elif breakpoint.type() == 'function':
      del self._breakpoints_by_function[breakpoint.function_name()]
    del self._breakpoints[breakpoint.id()]
    self._invalidate()
    self._listener.on_breakpoint_remove(breakpoint)
    # TODO(benvanik): remove from debuggers

  def _invalidate(self):
    """Marks the list as needing a save.
    The list will be saved at some point in the future.
    """
    self._is_dirty = True
    if not self._save_pending:
      # Queue a save for the next tick - this prevents excessive saving when
      # heavily manipulating breakpoints
      self._save_pending = True
      sublime.set_timeout(lambda: self.save(), 0)

  def invalidate_breakpoint(self, breakpoint):
    """Invalidates the given breakpoint.
    If any debuggers exist they will have the breakpoint refreshed.

    Args:
      breakpoint: Breakpoint that has changed.
    """
    self._invalidate()
    self._listener.on_breakpoint_change(breakpoint)
    print 'TODO: invalidate breakpoint'


class Breakpoint(object):
  """A breakpoint.
  Represents a stateful breakpoint that lives across sessions. Since breakpoints
  live longer than debugging sessions, the translation map resides within the
  debugger instance.
  """
  def __init__(self, breakpoint_list, breakpoint_id,
               location=None, function_name=None, *args, **kwargs):
    """Initializes a breakpoint.

    Args:
      breakpoint_list: Breakpoint list.
      breakpoint_id: Unique string ID.
      location: (uri, line, column) if a location-based breakpoint.
      function_name: Function name if a function-based breakpoint.
    """
    self._breakpoint_list = breakpoint_list
    self._id = breakpoint_id
    if location:
      self._type = 'location'
    else:
      self._type = 'function'
    if location:
      if type(location) == list:
        self._location = (location[0], location[1], location[2])
      else:
        self._location = location
    self._function_name = function_name or None
    self._display_name = None
    self._is_enabled = True
    self._condition = None
    self._ignore_count = 0

  def id(self):
    return self._id

  def type(self):
    return self._type

  def location(self):
    if self._type != 'location':
      return None
    return self._location

  def function_name(self):
    if self._type != 'function':
      return None
    return self._function_name

  def display_name(self):
    return self._display_name

  def set_display_name(self, value):
    if self._display_name == value:
      return
    self._display_name = value
    self._breakpoint_list.invalidate_breakpoint(self)

  def is_enabled(self):
    return self._is_enabled

  def set_enabled(self, value):
    if self._is_enabled == value:
      return
    self._is_enabled = value
    self._breakpoint_list.invalidate_breakpoint(self)

  def condition(self):
    return self._condition

  def set_condition(self, value):
    if self._condition == value:
      return
    self._condition = condition
    self._breakpoint_list.invalidate_breakpoint(self)

  def ignore_count(self):
    return self._ignore_count

  def set_ignore_count(self, value):
    if self._ignore_count == value:
      return
    self._ignore_count = value
    self._breakpoint_list.invalidate_breakpoint(self)
