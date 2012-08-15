# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


class State:
  ATTACHING = 0
  ATTACHED = 1
  DETACHED = 2


class EventListener(object):
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

  def on_break(self, location, breakpoints_hit, snapshot, *args, **kwargs):
    """Handles break events.

    Args:
      location: (uri, line, column) at active execution.
      breakpoints_hit: A list of Breakpoints that were triggered.
      snapshot: Current state snapshot.
    """
    pass

  def on_exception(self, location, is_uncaught, exception, snapshot,
                   *args, **kwargs):
    """Handles exception events.

    Args:
      location: (uri, line, column) at active execution.
      is_uncaught: True if the exception was uncaught.
      exception: Exception object.
      snapshot: Current state snapshot.
    """
    pass


class Debugger(object):
  """Stateful instance debugger.
  Controls a debugging session when attached to an instance.
  """
  def __init__(self, instance_info, protocol, listener, *args, **kwargs):
    self._instance_info = instance_info
    self._protocol = protocol
    self._protocol.set_detach_callback(self._on_detach)
    self._protocol.set_break_callback(self._on_break)
    self._protocol.set_exception_callback(self._on_exception)
    self._listener = listener
    self._listener._debugger = self
    self._target_window = None

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

  def _on_break(self, event, *args, **kwargs):
    """Handles protocol break callbacks.

    Args:
      event: BreakEvent from protocol.
    """
    print 'DEBUGGER: break event'
    snapshot = None
    self._set_is_running(False)
    self._listener.on_break(
        (event.source_url(), event.source_line(), event.source_column()),
        event.breakpoints(),
        snapshot)

  def _on_exception(self, event, *args, **kwargs):
    """Handles protocol exception callbacks.

    Args:
      event: ExceptionEvent from protocol.
    """
    print 'DEBUGGER: exception event'
    snapshot = None
    self._set_is_running(False)
    self._listener.on_exception(
        (event.source_url(), event.source_line(), event.source_column()),
        event.is_uncaught(),
        event.exception(),
        snapshot)

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

  def get_stacktrace(self):
    pass

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
    self._update_state(response)