# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


class InstanceInfo(object):
  """A debuggable application instance.
  Each instance represents a single process that can be debugged. Some providers
  may only have a single instance, where as others may have many (like a web
  browser that may have one per tab).
  """
  def __init__(self, provider, uri, *args, **kwargs):
    """Initializes an instance info.

    Args:
      provider: Instance provider.
      uri: Instance URI.
    """
    self._provider = provider
    self._uri = uri
    self._display_name = None
    self._display_info = None

  def provider(self):
    return self._provider

  def uri(self):
    return self._uri

  def display_name(self):
    return self._display_name or self._uri

  def set_display_name(self, value):
    self._display_name = value

  def display_info(self):
    if self._display_info:
      return self._display_info
    if not self._display_name:
      return None
    return self._uri

  def set_display_info(self, value):
    self._display_info = value

  def is_attached(self):
    return False

  # TODO(benvanik): icon url? get_icon()?

  def attach_debugger(self, listener):
    """Attaches a debugger to the given instance.
    The attaching happens asynchronously and may not be complete by the time
    this function returns.

    Args:
      listener: An DebuggerListener to receive events.

    Returns:
      A Debugger attached to the given instance, if it could be attached.
    """
    return self._provider.attach_debugger(self, listener)


class InstanceProvider(object):
  """An instance info provider.
  A hosting runtime or system that contains debuggable instances. Providers are
  long-lived and should try to reuse data.
  """
  def __init__(self, uri, *args, **kwargs):
    """Initializes a provider.

    Args:
      uri: Provider URI.
    """
    self._uri = uri
    self._display_name = None

  def uri(self):
    return self._uri

  def display_name(self):
    return self._display_name or self._uri

  def is_single_instance(self):
    return True

  def query_instances(self, callback):
    """Asynchronously queries active instances.
    This method must not block.

    Args:
      callback: A callback to receive a list of InstanceInfos.
    """
    raise NotImplementedError()

  def attach_debugger(self, instance_info, listener):
    """Attaches a debugger to the given instance.
    The attaching happens asynchronously and may not be complete by the time
    this function returns.

    Args:
      instance_info: Instance to attach to.
      listener: An DebuggerListener to receive events.

    Returns:
      A Debugger attached to the given instance, if it could be attached.
    """
    raise NotImplementedError()
