# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import json
import os
import sublime
import threading
import urllib2
from urlparse import urlparse

from .provider import InstanceInfo, InstanceProvider

class WebKitInstanceProvider(InstanceProvider):
  """An instance provider that represents a WebKit remote process.
  Chrome must be started with the '--remote-debugging-port=N' flag.
  Provider URIs are formed by:
    webkit://[hostname]:[port]
  So that the following Chrome command line:
    chrome --remote-debugging-port=9222
  Results in the following provider URI:
    webkit://localhost:9222
  """
  def __init__(self, uri, *args, **kwargs):
    super(WebKitInstanceProvider, self).__init__(uri, *args, **kwargs)
    parsed_uri = urlparse(uri)
    self._json_url = 'http://%s:%s/json' % (parsed_uri.hostname,
                                            parsed_uri.port)

  def is_single_instance(self):
    return False

  def query_instances(self, callback):
    def _json_fetched(content):
      if not content:
        callback(None)
        return

      # Parse instances
      try:
        json_obj = json.loads(content)
      except Exception, e:
        print 'WebKit: unable to parse instance JSON: %s' % (e)
        callback(None)
        return

      # Create instances
      instance_infos = []
      for info_obj in json_obj:
        instance_uri = info_obj.get('webSocketDebuggerUrl', None)
        if not instance_uri:
          continue
        instance_info = InstanceInfo(self, instance_uri)
        instance_info.set_display_name(info_obj.get('title', None))
        instance_info.set_display_info(info_obj.get('url', None))
        instance_infos.append(instance_info)

      # Done
      callback(instance_infos)

    # Kick of a thread to do the JSON fetch asynchronously
    thread = _WebKitFetchThread(self._json_url, _json_fetched)
    thread.start()

  def attach_debugger(self, instance_info, listener):
    raise NotImplementedError()


class _WebKitFetchThread(threading.Thread):
  """Thread that fetches the HTTP resource at the given URL.
  """
  def __init__(self, url, callback, *args, **kwargs):
    """Initializes a fetch thread.

    Args:
      url: HTTP URL to fetch.
      callback: Callback that will receive the text contents or None if an error
                occurred.
    """
    super(_WebKitFetchThread, self).__init__(*args, **kwargs)
    self._url = url
    self._callback = callback

  def _issue_callback(self, content):
    sublime.set_timeout(lambda: self._callback(content), 0)

  def run(self):
    # Attempt to open connection
    try:
      response = urllib2.urlopen(self._url)
    except Exception, e:
      print 'WebKit: error fetching %s: %s' % (self._url, e)
      self._issue_callback(None)
      return

    # Read contents
    try:
      content = response.read()
    except Exception, e:
      print 'WebKit: error reading %s: %s' % (self._url, e)
      response.close()
      self._issue_callback(None)
      return

    # Done!
    response.close()
    self._issue_callback(content)
