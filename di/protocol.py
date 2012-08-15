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


class ChangeSourceResponse(ProtocolResponse):
  """A response to change source requests.
  """
  def __init__(self, protocol, is_running, is_success, error_message, body,
               *args, **kwargs):
    """Initializes a change source response.

    Args:
      protocol: The protocol that this response is from.
      is_running: True if the VM is running.
      is_success: True if the requests was successful.
      error_message: An error message, if not successful.
      body: Raw body. Implementation-specific.
    """
    super(ChangeSourceResponse, self).__init__(
        protocol, is_running, is_success, error_message, body, *args, **kwargs)
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
  def __init__(self, protocol, source, breakpoints, *args, **kwargs):
    """Initializes a break protocol event.

    Args:
      protocol: The protocol that fired this event.
      source: A tuple of (url, line, column).
      breakpoints: A list of breakpoints that were hit, if any
    """
    super(BreakEvent, self).__init__(protocol, source, *args, **kwargs)
    self._breakpoints = breakpoints

  def breakpoints(self):
    return self._breakpoints


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