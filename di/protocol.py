# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


class DebuggerProtocol(object):
  """An abstract debugger protocol.
  Protocols implement asynchronous command channels for controlling remote
  debuggers. The debugging interface has been normalized (somewhat) and the
  exact transmission mechanism (TCP/pipes/etc) can be implemented however it is
  required.
  """
  def __init__(self, uri, *args, **kwargs):
    """Initializes a debugger protocol.

    Args:
      uri: Target instance URI.
    """
    self._uri = uri
    self._detach_callback = None
    self._break_callback = None
    self._exception_callback = None

  def uri(self):
    return self._uri

  def set_detach_callback(self, value):
    self._detach_callback = value

  def set_break_callback(self, value):
    self._break_callback = value

  def set_exception_callback(self, value):
    self._exception_callback = value

  def is_attached(self):
    """
    Returns:
      True if the protocol is attached.
    """
    raise NotImplementedError()

  def attach(self, callback=None):
    """Begins attaching the protocol to the instance.

    Args:
      callback: A function to call when the attaching completes.
                Receives a boolean indicating success.
    """
    raise NotImplementedError()

  def detach(self, terminate, reason=None):
    """Detaches the protocol from the instance.

    Args:
      terminate: True to terminate the target.
      reason: Reason for detaching, or None if user initiated.
    """
    raise NotImplementedError()

  def suspend(self, callback):
    """Suspends the target instance.
    Note that this will not break in the target, but merely suspend execution.

    Args:
      callback: A function to call when the suspend completes.
    """
    raise NotImplementedError()

  def resume(self, callback):
    """Resumes the target instance.
    If the target was at a breakpoint this will continue from there.

    Args:
      callback: A function to call when the resume completes.
    """
    raise NotImplementedError()

  def step(self, action, count, callback):
    """Steps the target instance.
    Only valid when suspended at a breakpoint.

    Args:
      action: 'next', 'in', 'out'.
      count: Number of steps to make.
      callback: A function to call when the step completes.
    """
    raise NotImplementedError()

  def change_source(self, uri, new_source, callback):
    """Modifies source code at runtime.
    Here be black magic, and it may not work.

    Args:
      uri: Source URI.
      new_source: New source code contents.
      callback: A function to call when the change completes.
    """
    raise NotImplementedError()

  def add_breakpoint(self, breakpoint, callback):
    """Adds a breakpoint to the debugger.

    Args:
      breakpoint: Breakpoint to add.
      callback: A function to call when the add completes. Inspect for the
                protocol ID used in change/remove requests.
    """
    raise NotImplementedError()

  def change_breakpoint(self, protocol_id, breakpoint, callback):
    """Updates a breakpoint that has changed.

    Args:
      protocol_id: Breakpoint protocol ID.
      breakpoint: Breakpoint that changed.
      callback: A function to call when the change completes.
    """
    raise NotImplementedError()

  def ignore_breakpoint(self, protocol_id, ignore_count, callback):
    """Ignores a breakpoint for a given number of hits.

    Args:
      protocol_id: Breakpoint protocol ID.
      ignore_count: Number of hits to ignore.
      callback: A function to call when the ignore acknowledges.
    """
    raise NotImplementedError()

  def remove_breakpoint(self, protocol_id, callback):
    """Removes a breakpoint from the debugger.

    Args:
      protocol_id: Breakpoint protocol ID.
      callback: A function to call when the remove completes.
    """
    raise NotImplementedError()

  def query_values(self, handle_ids, callback):
    """Queries the values of a list of handles.
    This is only valid while the remote debugger is paused after an event,
    such as a break or exception.

    Args:
      handle_ids: A list of handle IDs.
      callback: A function to call when the query completes.
    """
    raise NotImplementedError()

  def query_frame_scopes(self, frame, callback):
    """Queries the scopes for the given frame.
    This is only valid while the remote debugger is paused after an event,
    such as a break or exception.

    Args:
      frame: Frame to query.
      callback: A function to call when the query completes.
    """
    raise NotImplementedError()


class ProtocolResponse(object):
  """A response to a request made to a protocol.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               *args, **kwargs):
    """Initializes a protocol response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
    """
    self._protocol = protocol
    self._is_running = is_running
    self._is_success = is_success
    self._error_message = error_message
    self._body = body

  def is_running(self):
    return self._is_running

  def is_success(self):
    return self._is_success

  def error_message(self):
    return self._error_message

  def body(self):
    return self._body


class SnapshotResponse(ProtocolResponse):
  """A response containing callstack information.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               handle_set, frames, *args, **kwargs):
    """Initializes a snapshot response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
      handle_set: Handle value set.
      frames: A list of Frames.
    """
    super(SnapshotResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
    self._handle_set = handle_set
    self._frames = frames

  def handle_set(self):
    return self._handle_set

  def frames(self):
    return self._frames


class QueryValuesResponse(ProtocolResponse):
  """A response to value requests.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               handle_set, *args, **kwargs):
    """Initializes a value query response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
      handle_set: Handle value set.
    """
    super(QueryValuesResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
    self._handle_set = handle_set

  def handle_set(self):
    return self._handle_set


class QueryFrameScopesResponse(ProtocolResponse):
  """A response to frame scope value requests.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               handle_set, scopes, *args, **kwargs):
    """Initializes a frame scope query response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
      handle_set: Handle value set.
      scopes: A list of Scopes.
    """
    super(QueryFrameScopesResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
    self._handle_set = handle_set
    self._scopes = scopes

  def handle_set(self):
    return self._handle_set

  def scopes(self):
    return self._scopes


class ChangeSourceResponse(ProtocolResponse):
  """A response to change source requests.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               step_in_required, *args, **kwargs):
    """Initializes a change source response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
      step_in_required: A step-in is required.
    """
    super(ChangeSourceResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
    self._step_in_required = step_in_required
    # change_log: [
    #   {
    #     'break_points_update': [] ??
    #   },
    #   {
    #     'function_patched': ''
    #   },
    #   {
    #     'position_patched': [...]
    #   }
    # ],
    # result: {
    #   'stack_modified': bool,
    #   'updated': True,
    #   'change_tree': {
    #     'status': 'source changed',
    #     'name': '',
    #     'positions': {
    #       'start_position': 0,
    #       'end_position': 481
    #     },
    #     'new_positions': {
    #       'start_position': 0,
    #       'end_position': 482
    #     },
    #     'new_children': [],
    #     'children': [ ... ]
    #   },
    #   'textual_diff': {
    #     'old_len': 481,
    #     'new_len': 482,
    #     'chunks': [325, 325, 326]
    #   },
    #   'stack_update_needs_step_in': bool
    # }

  def step_in_required(self):
    return self._step_in_required


class AddBreakpointResponse(ProtocolResponse):
  """A response to add breakpoint requests.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               protocol_id, *args, **kwargs):
    """Initializes an add breakpoint response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
      protocol_id: Breakpoint protocol ID.
    """
    super(AddBreakpointResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
    self._protocol_id = protocol_id
    # TODO(benvanik): actual location line/col

  def protocol_id(self):
    return self._protocol_id


class ProtocolEvent(object):
  """An event fired by the protocol.
  """
  def __init__(self, protocol, source, *args, **kwargs):
    """Initializes a protocol event.

    Args:
      protocol: The protocol that fired this event.
      source: A tuple of (url, line, column).
    """
    self._protocol = protocol
    self._source = source

  def source_url(self):
    return self._source[0]

  def source_line(self):
    return self._source[1]

  def source_column(self):
    return self._source[2]


class BreakEvent(ProtocolEvent):
  """An event indicating that a break occurred.
  """
  def __init__(self, protocol, source, breakpoint_ids, *args, **kwargs):
    """Initializes a break protocol event.

    Args:
      protocol: The protocol that fired this event.
      source: A tuple of (url, line, column).
      breakpoint_ids: A list of breakpoints that were hit, if any.
    """
    super(BreakEvent, self).__init__(protocol, source, *args, **kwargs)
    self._breakpoint_ids = breakpoint_ids

  def breakpoint_ids(self):
    return self._breakpoint_ids


class ExceptionEvent(ProtocolEvent):
  """An event indicating that an exception occurred.
  """
  def __init__(self, protocol, source, is_uncaught, exception, *args, **kwargs):
    """Initializes an exception protocol event.

    Args:
      protocol: The protocol that fired this event.
      source: A tuple of (url, line, column).
      is_uncaught: True if the exception was uncaught.
      exception: Exception object.
    """
    super(ExceptionEvent, self).__init__(protocol, source, *args, **kwargs)
    self._is_uncaught = is_uncaught
    self._exception = exception

  def is_uncaught(self):
    return self._is_uncaught

  def exception(self):
    return self._exception


class Frame(object):
  def __init__(self, ordinal, location, is_constructor, is_at_return,
               function_ref, this_ref, argument_vars, local_vars):
    self._ordinal = ordinal
    self._location = location
    self._is_constructor = is_constructor
    self._is_at_return = is_at_return
    self._function_ref = function_ref
    self._this_ref = this_ref
    self._arguments = argument_vars
    self._locals = local_vars

  def ordinal(self):
    return self._ordinal

  def location(self):
    return self._location

  def is_constructor(self):
    return self._is_constructor

  def is_at_return(self):
    return self._is_at_return

  def function_ref(self):
    return self._function_ref

  def this_ref(self):
    return self._this_ref

  def argument_refs(self):
    return self._arguments

  def local_refs(self):
    return self._locals


class ScopeType:
  GLOBAL = 0
  LOCAL = 1
  WITH = 2
  CLOSURE = 3
  CATCH = 4


class Scope(object):
  def __init__(self, ordinal, scope_type, object_ref, *args, **kwargs):
    self._ordinal = ordinal
    self._scope_type = scope_type
    self._object_ref = object_ref

  def ordinal(self):
    return self._ordinal

  def scope_type(self):
    return self._scope_type

  def object_ref(self):
    return self._object_ref


class HandleSet(object):
  def __init__(self, *args, **kwargs):
    self._values = {}

  def merge(self, other):
    for value in other._values:
      self.add_value(value)

  def add_value(self, value):
    self._values[value.handle_id()] = value

  def has_value(self, handle_id):
    return self._values.get(handle_id, None) != None

  def get_value(self, handle_id):
    return self._values.get(handle_id, None)

  def dump(self):
    print 'handle set contains %s values:' % (len(self._values.keys()))
    for (key, value) in self._values.items():
      print '  %s: %s' % (key, value)

  def print_value(self, key, handle_id):
    dumper = _RecursiveDumper(self)
    dumper.dump(key, self.get_value(handle_id))


class _RecursiveDumper(object):
  def __init__(self, handle_set):
    self._handle_set = handle_set
    self._stack = []

  def dump(self, key, value):
    indent = ''.join(['  ' for n in range(len(self._stack))])
    print '%s%s: %s' % (indent, key, value)
    if value in self._stack:
      return
    if isinstance(value, JSObject):
      self._stack.append(value)
      if isinstance(value, JSFunction):
        self._dump_function(value)
      else:
        self._dump_object(value)
      self._stack.pop()

  def _dump_function(self, value):
    pass

  def _dump_object(self, value):
    for p in value.properties():
      self.dump(p.name(), self._handle_set.get_value(p.ref()))
    pass


class JSHandle(object):
  def __init__(self, handle_id, handle_type, *args, **kwargs):
    self._handle_id = handle_id
    self._handle_type = handle_type

  def handle_id(self):
    return self._handle_id

  def handle_type(self):
    return self._handle_type


class JSUndefined(JSHandle):
  def __init__(self, handle_id, *args, **kwargs):
    super(JSUndefined, self).__init__(handle_id, 'undefined', *args, **kwargs)

  def __repr__(self):
    return 'undefined'


class JSNull(JSHandle):
  def __init__(self, handle_id, *args, **kwargs):
    super(JSNull, self).__init__(handle_id, 'null', *args, **kwargs)

  def __repr__(self):
    return 'null'


class JSBoolean(JSHandle):
  def __init__(self, handle_id, value, *args, **kwargs):
    super(JSBoolean, self).__init__(handle_id, 'boolean', *args, **kwargs)
    self._value = value

  def value(self):
    return self._value

  def __repr__(self):
    return 'true' if self._value else 'false'


class JSNumber(JSHandle):
  def __init__(self, handle_id, value, *args, **kwargs):
    super(JSNumber, self).__init__(handle_id, 'number', *args, **kwargs)
    self._value = value

  def value(self):
    return self._value

  def __repr__(self):
    return str(self._value)


class JSString(JSHandle):
  def __init__(self, handle_id, value, *args, **kwargs):
    super(JSString, self).__init__(handle_id, 'string', *args, **kwargs)
    self._value = value

  def value(self):
    return self._value

  def __repr__(self):
    return '"%s"' % (self._value)


class JSScript(JSHandle):
  def __init__(self, handle_id, uri, *args, **kwargs):
    super(JSScript, self).__init__(handle_id, 'script', *args, **kwargs)
    self._uri = uri

  def uri(self):
    return self._uri

  def __repr__(self):
    return self._uri


class JSObject(JSHandle):
  def __init__(self, handle_id, class_name, constructor_ref, prototype_ref,
               properties, *args, **kwargs):
    super(JSObject, self).__init__(handle_id, 'object', *args, **kwargs)
    self._class_name = class_name
    self._constructor_ref = constructor_ref
    self._prototype_ref = prototype_ref
    self._properties = properties

  def class_name(self):
    return self._class_name

  def constructor_ref(self):
    return self._constructor_ref

  def prototype_ref(self):
    return self._prototype_ref

  def properties(self):
    return self._properties

  def __repr__(self):
    return '<object %s>' % (self.handle_id())


class JSProperty(object):
  def __init__(self, name, ref, property_type, attributes, *args, **kwargs):
    self._name = name
    self._ref = ref
    self._property_type = property_type
    self._attributes = attributes

  def name(self):
    return self._name

  def ref(self):
    return self._ref

  def property_type(self):
    return self._property_type

  def attributes(self):
    return self._attributes

  def __repr__(self):
    return '%s = <%s>' % (self._name, self._ref)


class JSFunction(JSObject):
  def __init__(self, handle_id, class_name, constructor_ref, prototype_ref,
               properties, name, inferred_name, location, *args, **kwargs):
    super(JSFunction, self).__init__(handle_id, class_name, constructor_ref,
                                     prototype_ref, properties, *args, **kwargs)
    self._name = name
    self._inferred_name = inferred_name
    self._location = location

  def name(self):
    return self._name

  def inferred_name(self):
    return self._inferred_name

  def location(self):
    return self._location

  def __repr__(self):
    name = self._inferred_name or self._name
    return '%s (%s@%s:%s)' % (name, self._location[0], self._location[1],
                              self._location[2])
