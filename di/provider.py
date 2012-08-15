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

  def provider(self):
    return self._provider

  def uri(self):
    return self._uri

  def display_name(self):
    return self._display_name or self._uri

  def set_display_name(self, value):
    self._display_name = value

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
  A hosting runtime or system that contains debuggable instances. Providers,
  once created, should asynchronously update their active instances frequently.
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

  def refresh(self):
    """Forces a refresh of the provider.
    """
    pass

  def get_current_instances(self):
    """Gets a cached list of active instances.
    This method must not block. It should return the list of instances from the
    last time the provider was queried.

    Returns:
      A list of InstanceInfos provided.
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
