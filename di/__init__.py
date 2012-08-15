# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


from urlparse import urlparse

import debugger
from debugger import EventListener
import provider
import util
import v8


__all__ = [
    'create_provider',
    'cleanup_module',
    'EventListener'
    ]


provider_types = {
    'v8': v8.V8InstanceProvider,
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


def cleanup_module():
  """Cleans up the module before a reload.
  This will close all debugger connections and prepare the module for reloading.
  """
  util.close_open_protocols()
