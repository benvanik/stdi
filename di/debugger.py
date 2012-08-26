# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


class State:
  ATTACHING = 0
  ATTACHED = 1
  DETACHED = 2


class Snapshot(object):
  """Debug state snapshot.
  """
  def __init__(self, location, handle_set, frames, *args, **kwargs):
    """Initializes a debug snapshot.

    Args:
      location: (uri, line, column) location.
      handle_set: Handle value set, holding all handles.
      frames: A list of Frames.
    """
    self._location = location
    self._handle_set = handle_set
    self._frames = frames

  def location(self):
    return self._location

  def handle_set(self):
    return self._handle_set

  def frames(self):
    return self._frames


class DebuggerListener(object):
  """Debugger event listener.
  Receives debugger event notifications.
  """
  def __init__(self, *args, **kwargs):
    self._debugger = None

  def debugger(self):
    return self._debugger

  def on_attach(self, *args, **kwargs):
    """Handles the debugger successfully attaching to an instance.
    """
    pass

  def on_detach(self, reason, *args, **kwargs):
    """Handles the debugger detaching from the instance.

    Args:
      reason: Reason string.
    """
    # TODO(benvanik): reason code
    pass

  def on_suspend(self, *args, **kwargs):
    """Handles the target instance entering the paused state.
    """
    pass

  def on_resume(self, *args, **kwargs):
    """Handles the target instance entering the running state.
    """
    pass

  def on_snapshot(self, snapshot, *args, **kwargs):
    """Handles snapshot updates.

    Args:
      snapshot: Current state snapshot.
    """
    pass

  def on_break(self, location, breakpoints_hit, *args, **kwargs):
    """Handles break events.

    Args:
      location: (uri, line, column) at active execution.
      breakpoints_hit: A list of Breakpoints that were triggered.
    """
    pass

  def on_exception(self, location, is_uncaught, exception,
                   *args, **kwargs):
    """Handles exception events.

    Args:
      location: (uri, line, column) at active execution.
      is_uncaught: True if the exception was uncaught.
      exception: Exception object.
    """
    pass


class Debugger(object):
  """Stateful instance debugger.
  Controls a debugging session when attached to an instance.
  """
  def __init__(self, instance_info, protocol, listener, *args, **kwargs):
    """Initializes a debugger.

    Args:
      instance_info: Target instance info.
      protocol: Protocol used for communicating.
      listener: DebuggerListener to receive events.
    """
    self._instance_info = instance_info
    self._protocol = protocol
    self._protocol.set_detach_callback(self._on_detach)
    self._protocol.set_break_callback(self._on_break)
    self._protocol.set_exception_callback(self._on_exception)
    self._listener = listener
    self._listener._debugger = self
    self._target_window = None

    # Maps of Breakpoint.id() -> protocol IDs and vs.
    self._breakpoint_to_protocol = {}
    self._protocol_to_breakpoint = {}
    # A queue of pending breakpoint commands as (type, breakpoint)
    # The queue is used to make change/removes wait until adds have completed
    # and an ID mapping exists
    self._breakpoint_queue = []

    self._state = State.ATTACHING
    self._is_running = False

  def provider(self):
    return self._instance_info.provider()

  def instance_info(self):
    return self._instance_info

  def protocol(self):
    return self._protocol

  def target_window(self):
    return self._target_window

  def set_target_window(self, value):
    self._target_window = value

  def state(self):
    return self._state

  def is_running(self):
    return self._is_running

  def _set_is_running(self, value):
    if self._is_running != value:
      self._is_running = value
      if self._is_running:
        self._listener.on_resume()
      else:
        self._listener.on_suspend()

  def _update_state(self, response):
    self._set_is_running(response.is_running())

  def is_attached(self):
    """
    Returns:
      True if the debugger is attached to the instance.
      This will be false while the debugger is attaching or if the session has
      ended.
    """
    return self._state == State.ATTACHED

  def attach(self):
    """Attaches the debugger to the target instance.
    """
    self._protocol.attach(self._on_attach)

  def _on_attach(self, *args, **kwargs):
    """Handles protocol attach callbacks.
    """
    self._state = State.ATTACHED
    self._set_is_running(True)
    self._listener.on_attach()

  def detach(self, terminate=True):
    """Detaches the debugger from the target instance.

    Args:
      terminate: True to attempt to terminate the target.
    """
    self._protocol.detach(terminate)

  def _on_detach(self, reason, *args, **kwargs):
    """Handles protocol detach callbacks.

    Args:
      reason: Reason message or None if user initiated.
    """
    self._state = State.DETACHED
    self._set_is_running(False)
    self._listener.on_detach(reason)

  def _pre_event(self, event, callback, *args, **kwargs):
    def _on_query_state(response):
      self._set_is_running(False)
      location = (event.source_url(), event.source_line(),
                  event.source_column())
      snapshot = Snapshot(location,
                          response.handle_set(),
                          response.frames())
      self._listener.on_snapshot(snapshot)
      callback(location)
    self._protocol.query_state(_on_query_state)

  def _on_break(self, event, *args, **kwargs):
    """Handles protocol break callbacks.

    Args:
      event: BreakEvent from protocol.
    """
    print 'DEBUGGER: break event'
    def _handle_event(location):
      breakpoints = []
      protocol_ids = event.breakpoint_ids()
      for protocol_id in protocol_ids:
        breakpoint = self._protocol_to_breakpoint.get(protocol_id, None)
        if breakpoint:
          breakpoints.append(breakpoint)
      self._listener.on_break(location, breakpoints)
    self._pre_event(event, _handle_event, *args, **kwargs)

  def _on_exception(self, event, *args, **kwargs):
    """Handles protocol exception callbacks.

    Args:
      event: ExceptionEvent from protocol.
    """
    print 'DEBUGGER: exception event'
    def _handle_event(location):
      self._listener.on_exception(location, event.is_uncaught(),
                                  event.exception())
    self._pre_event(event, _handle_event, *args, **kwargs)

  def suspend(self):
    if not self._is_running:
      return
    print 'DEBUGGER: suspend'
    self._protocol.suspend(self._on_suspend)
    self._set_is_running(False)

  def _on_suspend(self, response, *args, **kwargs):
    print 'DEBUGGER: suspended: %s' % (response)
    self._update_state(response)

  def can_suspend(self):
    return self._is_running

  def resume(self):
    if self._is_running:
      return
    print 'DEBUGGER: resume'
    self._protocol.resume(self._on_resume)
    self._set_is_running(True)

  def _on_resume(self, response, *args, **kwargs):
    print 'DEBUGGER: resumed: %s' % (response)
    self._update_state(response)

  def can_resume(self):
    return not self._is_running

  def _step(self, action, count=1):
    if self._is_running:
      return
    self._protocol.step(action, count, self._on_step)

  def _on_step(self, response, *args, **kwargs):
    print 'DEBUGGER: stepped: %s' % (response)
    self._update_state(response)

  def step_over(self):
    print 'DEBUGGER: step over'
    self._step('next')

  def can_step_over(self):
    return not self._is_running

  def step_in(self):
    print 'DEBUGGER: step in'
    self._step('in')

  def can_step_in(self):
    return not self._is_running

  def step_out(self):
    print 'DEBUGGER: step out'
    self._step('out')

  def can_step_out(self):
    return not self._is_running

  def continue_to(self):
    print 'DEBUGGER: continue to'
    pass

  def can_continue_to(self):
    return True

  def evaluate(self):
    pass

  def can_evaluate(self):
    return True

  def query_values(self, handle_ids, callback):
    if self._is_running:
      return
    print 'DEBUGGER: query handle values'
    self._protocol.query_values(handle_ids, lambda response: callback(
        response.handle_set()))

  def query_frame_scopes(self, frame, callback):
    if self._is_running:
      return
    print 'DEBUGGER: query frame scopes'
    self._protocol.query_frame_scopes(frame, lambda response: callback(
        response.handle_set(), response.scopes()))

  def force_gc(self):
    pass

  def change_source(self, uri, new_source):
    # Pass off the change request to the protocol - it will perform the change
    # if required
    self._protocol.change_source(uri, new_source, self._on_change_source)

  def _on_change_source(self, response, *args, **kwargs):
    print 'DEBUGGER: changed source'
    # TODO(benvanik): pass up the delta to the listener - it may need to
    #                 highlight files if changes could not be made/etc
    # TODO(benvanik): breakpoint fixup?
    self._update_state(response)

    # If the VM requested a step-in, step-in
    if response.step_in_required():
      self.step_in()

  def add_breakpoint(self, breakpoint):
    """Adds a breakpoint to the debugger.

    Args:
      breakpoint: Breakpoint to add.
    """
    print 'DEBUGGER: add breakpoint'
    def _on_add_breakpoint(response, *args, **kwargs):
      # TODO(benvanik): update actual location
      breakpoint_id = breakpoint.id()
      protocol_id = response.protocol_id()
      self._breakpoint_to_protocol[breakpoint_id] = protocol_id
      self._protocol_to_breakpoint[protocol_id] = breakpoint
      self._pump_breakpoint_queue()
      self._update_state(response)
    self._protocol.add_breakpoint(breakpoint, _on_add_breakpoint)

  def change_breakpoint(self, breakpoint):
    """Updates a breakpoint that has changed.

    Args:
      breakpoint: Breakpoint that changed.
    """
    print 'DEBUGGER: change breakpoint'
    self._breakpoint_queue.append(('change', breakpoint))
    self._pump_breakpoint_queue()

  def _on_change_breakpoint(self, response, *args, **kwargs):
    print 'DEBUGGER: changed breakpoint'
    self._update_state(response)

  def ignore_breakpoint(self, breakpoint, ignore_count):
    """Ignores a breakpoint for a number of hits.

    Args:
      breakpoint: Breakpoint to ignore.
      ignore_count: Number of hits to ignore.
    """
    print 'DEBUGGER: ignore breakpoint'
    self._breakpoint_queue.append(('ignore', breakpoint, ignore_count))
    self._pump_breakpoint_queue()

  def _on_ignore_breakpoint(self, response, *args, **kwargs):
    print 'DEBUGGER: ignored breakpoint'
    self._update_state(response)

  def remove_breakpoint(self, breakpoint):
    """Removes a breakpoint from the debugger.

    Args:
      breakpoint: Breakpoint to remove.
    """
    print 'DEBUGGER: remove breakpoint'
    self._breakpoint_queue.append(('remove', breakpoint))
    self._pump_breakpoint_queue()

  def _on_remove_breakpoint(self, response, *args, **kwargs):
    print 'DEBUGGER: removed breakpoint'
    self._update_state(response)

  def _pump_breakpoint_queue(self):
    """Executes all breakpoint queue entries until the first without a mapping.
    This should be called after every entry is added to ensure they are all
    flushed.
    """
    while len(self._breakpoint_queue):
      entry = self._breakpoint_queue[0]
      breakpoint = entry[1]
      protocol_id = self._breakpoint_to_protocol.get(breakpoint.id(), None)
      if protocol_id == None:
        break
      if entry[0] == 'change':
        self._protocol.change_breakpoint(protocol_id, breakpoint,
                                         self._on_change_breakpoint)
      elif entry[0] == 'ignore':
        self._protocol.ignore_breakpoint(protocol_id, entry[2],
                                         self._on_ignore_breakpoint)
      elif entry[0] == 'remove':
        self._protocol.remove_breakpoint(protocol_id,
                                         self._on_remove_breakpoint)
        del self._breakpoint_to_protocol[breakpoint.id()]
        del self._protocol_to_breakpoint[protocol_id]
      self._breakpoint_queue.pop(0)

  # TODO(benvanik): toggle all breakpoints
