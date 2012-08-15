# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


# NOTE: this file, when modified, may break things if ST is running


# All open protocols - used for global cleanup
_open_protocols = []


def register_open_protocol(protocol):
  """Registers a protocol for global cleanup.
  The protocol will be detached before the plugin is reloaded.
  This ensures that connections are cleaned up correctly/etc and life is easy.

  Args:
    protocol: Protocol.
  """
  global _open_protocols
  _open_protocols.append(protocol)


def close_open_protocols():
  """Detaches all open protocols.
  """
  global _open_protocols
  for protocol in _open_protocols:
    protocol.detach(terminate=False)
  _open_protocols = []
