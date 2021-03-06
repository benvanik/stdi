# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


from urlparse import urlparse

import breakpoints
from breakpoints import BreakpointListener
import debugger
from debugger import DebuggerListener
import provider
import util
import v8
import webkit


__all__ = [
    'create_provider',
    'load_breakpoint_list',
    'cleanup_module',
    'BreakpointListener',
    'DebuggerListener',
    ]


provider_types = {
    'v8': v8.V8InstanceProvider,
    'webkit': webkit.WebKitInstanceProvider,
    }


def create_provider(uri):
  """Creates a provider for the given URI.
  The scheme of the URI is used to pick which provider to use. Providers act
  asynchronously and may take time to provide their instances.

  Args:
    uri: Provider URI.

  Returns:
    A new InstanceProvider.
  """
  parsed_uri = urlparse(uri)
  provider_type = provider_types.get(parsed_uri.scheme, None)
  if not provider_type:
    return None
  return provider_type(uri)


def load_breakpoint_list(path, listener):
  """Loads (or creates) a breakpoint list.
  A breakpoint list should live for the entire lifetime of the editor and be
  used to manage all breakpoint related tasks.

  Args:
    path: Breakpoint settings file path.
    listener: BreakpointListener to receive events.

  Returns:
    A BreakpointList for managing breakpoints across all debuggers.
  """
  breakpoint_list = breakpoints.BreakpointList(listener)
  breakpoint_list.load(path)
  return breakpoint_list


def cleanup_module():
  """Cleans up the module before a reload.
  This will close all debugger connections and prepare the module for reloading.
  """
  util.close_open_protocols()
