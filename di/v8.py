# Copyright 2012 Google Inc. All Rights Reserved.

__author__ = 'benvanik@google.com (Ben Vanik)'


import json
import os
import socket
import sublime
import threading
from urlparse import urlparse
import Queue

from .util import register_open_protocol
from .debugger import Debugger
from .protocol import *
from .provider import InstanceInfo, InstanceProvider


def _transform_node_source(source):
  """Transforms a source file into the same format node.js expects.

  Args:
    source: Source file contents.

  Returns:
    Transformed contents.
  """
  wrapped = ('(function (exports, require, module, __filename, __dirname) {'
             ' %s });') % (source)
  return wrapped.replace('\n', os.linesep)


class V8InstanceProvider(InstanceProvider):
  """An instance provider that represents a v8 process.
  V8 must be started with the '--debug' flag (or '--debug=N' to specify a port).
  Provider URIs are formed by:
    v8://[hostname]:[port]
  So that the following node command line:
    node --debug=5858 script.js
  Results in the following provider URI:
    v8://localhost:5858
  """
  def __init__(self, uri, *args, **kwargs):
    super(V8InstanceProvider, self).__init__(uri, *args, **kwargs)
    self._instances = [
        InstanceInfo(self, uri),
        ]

  def is_single_instance(self):
    return True

  def query_instances(self, callback):
    sublime.set_timeout(lambda: callback(self._instances), 0)

  def attach_debugger(self, instance_info, listener):
    protocol = V8DebuggerProtocol(instance_info.uri())
    return Debugger(instance_info, protocol, listener)


class V8DebuggerProtocol(DebuggerProtocol):
  """A debugger protocol that talks to a V8 instance.
  """
  def __init__(self, uri, *args, **kwargs):
    super(V8DebuggerProtocol, self).__init__(uri, *args, **kwargs)
    self._seq_id = 0
    self._attach_callback = None
    self._pending_callbacks = {}
    self._recv_queue = Queue.Queue()
    self._socket = None
    self._thread = None

  def attach(self, callback=None):
    print 'V8: attach'
    self._attach_callback = callback
    self._state = 1
    parsed_uri = urlparse(self.uri())
    address = (parsed_uri.hostname, parsed_uri.port)
    # TODO(benvanik): make this async
    try:
      self._socket = socket.create_connection(address, None)
    except socket.error, e:
      if e.errno == 61 or e.errno == 10061:
        if self._detach_callback:
          self._detach_callback('Unable to connect')
        return
      else:
        raise
    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    self._thread = _V8ProtocolThread(self, self._socket)
    self._thread.start()
    self._send_command('version')
    register_open_protocol(self)

  def detach(self, terminate, reason=None):
    if not self._socket:
      return
    print 'V8: detach: %s' % (reason)
    try:
      if terminate:
        # TODO(benvanik): some pluggable agnostic way
        self._send_command('evaluate', {
            'expression': 'process.exit(0)',
            'global': True
            })
      self._send_command('disconnect')
      self._socket.shutdown(0)
      self._socket.close()
    except:
      pass
    self._socket = None
    self._thread = None
    if self._detach_callback:
      self._detach_callback(reason)

  def query_state(self, callback):
    print 'V8: query_state'
    self._send_command('backtrace', {
        'fromFrame': 0,
        'toFrame': 1024,
        }, lambda response: callback(response))

  def suspend(self, callback):
    print 'V8: suspend'
    self._send_command('suspend', {})
    self._send_command('backtrace', {
        'fromFrame': 0,
        'toFrame': 1024,
        }, lambda response: callback(response))

  def resume(self, callback):
    print 'V8: resume'
    self._send_command('continue', {}, lambda response: callback(response))

  def step(self, action, count, callback):
    print 'V8: step %s (x%s)' % (action, count)
    self._send_command('continue', {
        'stepaction': action,
        'stepcount': count,
        })
    self._send_command('backtrace', {
        'fromFrame': 0,
        'toFrame': 1024,
        }, lambda response: callback(response))

  def change_source(self, uri, new_source, callback):
    # Hacky quick-exit for non-JS files - this should be tuned
    if uri[len(uri) - 3:] != '.js':
      return

    print 'V8: change source %s' % (uri)
    def _got_scripts(response, *args, **kwargs):
      script_entries = response.body()
      if not script_entries or not len(script_entries):
        # Script not found - nothing to do?
        return
      if len(script_entries) != 1:
        # Too many scripts found? Cannot do this ambiguously
        print 'V8: change_source found multiple matching scripts, aborting'
        return
      script_id = int(script_entries[0]['id'])
      transformed_source = _transform_node_source(new_source)
      self._send_command('changelive', {
          'script_id': script_id,
          'preview_only': False,
          'new_source': transformed_source,
          }, lambda response: callback(response))
    self._send_command('scripts', {
        'includeSource': True, #False,
        'filter': uri,
        }, _got_scripts)

  def add_breakpoint(self, breakpoint, callback):
    print 'V8: add breakpoint %s' % (breakpoint.id())
    if breakpoint.type() == 'location':
      breakpoint_type = 'script'
      location = breakpoint.location()
      (target, target_line, target_column) = location
    elif breakpoint.type() == 'function':
      breakpoint_type = 'function'
      target = breakpoint.function_name()
      target_line = 0
      target_column = 0
    self._send_command('setbreakpoint', {
        'type': breakpoint_type,
        'target': target,
        'line': target_line - 1,
        'column': target_column - 1,
        'enabled': breakpoint.is_enabled(),
        'condition': breakpoint.condition(),
        }, lambda response: callback(response))

  def change_breakpoint(self, protocol_id, breakpoint, callback):
    print 'V8: change breakpoint p%s/%s' % (protocol_id, breakpoint.id())
    self._send_command('changebreakpoint', {
        'breakpoint': protocol_id,
        'enabled': breakpoint.is_enabled(),
        'condition': breakpoint.condition(),
        }, lambda response: callback(response))

  def ignore_breakpoint(self, protocol_id, ignore_count, callback):
    print 'V8: ignore breakpoint p%s' % (protocol_id)
    self._send_command('changebreakpoint', {
        'breakpoint': protocol_id,
        'ignoreCount': ignore_count,
        }, lambda response: callback(response))

  def remove_breakpoint(self, protocol_id, callback):
    print 'V8: remove breakpoint p%s' % (protocol_id)
    self._send_command('clearbreakpoint', {
        'breakpoint': protocol_id,
        }, lambda response: callback(response))

  def query_values(self, handle_ids, callback):
    print 'V8: query values %s' % (handle_ids)
    self._send_command('lookup', {
        'handles': handle_ids,
        }, lambda response: callback(response))

  def query_frame_scopes(self, frame, callback):
    print 'V8: query frame %s scopes' % (frame.ordinal())
    def _on_scopes(response):
      print 'V8: scopes result'
      callback(response)
    self._send_command('scopes', {
        'frameNumber': frame.ordinal(),
        }, _on_scopes)

  def _send_command(self, command, arguments=None, callback=None):
    """Sends a command to the debugger.

    Args:
      command: Command name (like 'continue').
      command_obj: A dict of command parameters.
      callback: Optional callback function to receive the result.
    """
    seq_id = self._seq_id
    self._seq_id += 1
    command_obj = {
        'seq': seq_id,
        'type': 'request',
        'command': command,
        }
    if arguments:
      command_obj['arguments'] = arguments
    if callback:
      self._pending_callbacks[seq_id] = callback

    command_str = json.dumps(command_obj)
    command_encoded = command_str.encode('utf-8')
    content_length = len(command_encoded)
    packet_str = u'Content-Length: %s\r\n\r\n%s' % (content_length,
                                                    command_encoded)
    print 'V8 send: %s' % (command_encoded)
    self._socket.sendall(packet_str)

  def queue_recv_from_thread(self, recv_obj):
    """Queues a receive from a background thread.
    This method is thread safe.

    Args:
      recv_obj: JSON object from the packet.
    """
    self._recv_queue.put_nowait(recv_obj)
    sublime.set_timeout(self._process_recv_queue, 0)

  def _process_recv_queue(self):
    """Handles the incoming receive queue on the main thread.
    """
    while not self._recv_queue.empty():
      recv_obj = self._recv_queue.get_nowait()
      if recv_obj['type'] == 'response':
        # Response - ignore those that have no request_seq (we can't match them
        # to their callbacks without it)
        # Special case for version/attach callback
        if recv_obj['command'] == 'version':
          if self._attach_callback:
            self._attach_callback()
            self._attach_callback = None
            continue
        if not 'request_seq' in recv_obj:
          continue
        self._handle_response(recv_obj)
      elif recv_obj['type'] == 'event':
        if recv_obj['event'] == 'break':
          # Break - either unconditional ('debugger;') or a breakpoint
          self._handle_break_event(recv_obj)
        elif recv_obj['event'] == 'exception':
          # Exception (unhandled/first-throw, etc)
          self._handle_exception_event(recv_obj)

  def _handle_response(self, recv_obj):
    """Handles a response from the remote debugger.

    Args:
      recv_obj: JSON object from the packet.
    """
    print 'V8: incoming response: %s' % (recv_obj)
    seq_id = int(recv_obj['request_seq'])
    running = recv_obj.get('running', False)
    success = recv_obj.get('success', False)
    message = recv_obj.get('message', None)
    body = recv_obj.get('body', None)
    args = [self, running, success, message, body]

    # TODO(benvanik): a cleaner way of adding properties/etc
    # print json.dumps(recv_obj, indent=2)
    response_type = ProtocolResponse
    kwargs = {}
    response_command = recv_obj.get('command', '')
    # if response_command == 'evaluate':
    #   response_type = EvaluateResponse
    #   kwargs = {}
    if response_command == 'lookup':
      response_type = QueryValuesResponse
      handle_set = HandleSet()
      self._populate_handle_set_from_map(handle_set, body)
      kwargs = {
          'handle_set': handle_set,
          }
    elif response_command == 'scopes':
      response_type = QueryFrameScopesResponse
      handle_set = HandleSet()
      ref_objs = recv_obj.get('refs', [])
      self._populate_handle_set_from_list(handle_set, ref_objs)
      scopes = []
      for scope_info in body['scopes']:
        scopes.append(Scope(scope_info['index'], scope_info['type'],
                            scope_info['object']['ref']))
      kwargs = {
          'handle_set': handle_set,
          'scopes': scopes,
          }
    elif response_command == 'backtrace':
      response_type = SnapshotResponse
      handle_set = HandleSet()
      ref_objs = recv_obj.get('refs', [])
      self._populate_handle_set_from_list(handle_set, ref_objs)
      frames = []
      for frame_obj in body.get('frames', []):
        frames.append(self._parse_frame(frame_obj, handle_set))
      kwargs = {
          'handle_set': handle_set,
          'frames': frames,
          }
    elif response_command == 'changelive':
      response_type = ChangeSourceResponse
      kwargs = {
          'step_in_required': body.get('stepin_recommended', False),
          }
    elif response_command == 'setbreakpoint':
      response_type = AddBreakpointResponse
      # TODO(benvanik): extract 'actual_locations': ['column':, 'line':,]
      kwargs = {
          'protocol_id': body['breakpoint'],
          }
    response = response_type(*args, **kwargs)

    callback = self._pending_callbacks.get(seq_id, None)
    if callback:
      del self._pending_callbacks[seq_id]
      callback(response)

  def _populate_handle_set_from_map(self, handle_set, ref_obj_map):
    for (key, ref_obj) in ref_obj_map.items():
      self._add_handle_to_set(handle_set, ref_obj)

  def _populate_handle_set_from_list(self, handle_set, ref_objs):
    # Pre-pass to find all scripts by ID
    script_uris = {}
    for ref_obj in ref_objs:
      if ref_obj['type'] == 'script':
        script_uris[ref_obj['id']] = ref_obj['name']

    for ref_obj in ref_objs:
      self._add_handle_to_set(handle_set, ref_obj)

  def _add_handle_to_set(self, handle_set, ref_obj):
    def _parse_properties(properties_obj):
      properties = []
      for property_obj in properties_obj:
        properties.append(JSProperty(
            property_obj['name'],
            property_obj['ref'],
            property_obj.get('propertyType', 0),
            property_obj.get('attributes', 0)))
      return properties

    handle_id = ref_obj['handle']
    handle_type = ref_obj['type']
    if handle_type == 'undefined':
      handle = JSUndefined(handle_id)
    elif handle_type == 'null':
      handle = JSNull(handle_id)
    elif handle_type == 'boolean':
      handle = JSBoolean(handle_id, ref_obj['value'])
    elif handle_type == 'number':
      handle = JSNumber(handle_id, ref_obj['value'])
    elif handle_type == 'string':
      handle = JSString(handle_id, ref_obj['value'])
    elif handle_type == 'script':
      handle = JSScript(handle_id, ref_obj['name'])
    elif handle_type == 'object':
      handle = JSObject(
          handle_id,
          ref_obj['className'],
          ref_obj['constructorFunction']['ref'],
          ref_obj['prototypeObject']['ref'],
          _parse_properties(ref_obj['properties']))
    elif handle_type == 'function':
      location = None
      if 'scriptId' in ref_obj:
        #print ref_obj['scriptId']
        #print script_uris
        #uri = script_uris[ref_obj['scriptId']]
        #location = (uri, ref_obj['line'] + 1, ref_obj['column'] + 1)
        pass
      handle = JSFunction(
          handle_id,
          ref_obj['className'],
          ref_obj['constructorFunction']['ref'],
          ref_obj['prototypeObject']['ref'],
          _parse_properties(ref_obj['properties']),
          ref_obj['name'],
          ref_obj['inferredName'],
          location)
    handle_set.add_value(handle)

  def _parse_frame(self, frame_obj, handle_set):
    script = handle_set.get_value(frame_obj['script']['ref'])
    uri = script.uri()
    location = (uri, frame_obj['line'] + 1, frame_obj['column'] + 1)
    argument_vars = []
    for var in frame_obj['arguments']:
      argument_vars.append((var.get('name', None), var['value']['ref']))
    local_vars = []
    for var in frame_obj['locals']:
      local_vars.append((var['name'], var['value']['ref']))
    frame = Frame(
        frame_obj['index'],
        location,
        frame_obj['constructCall'],
        frame_obj['atReturn'],
        frame_obj['func']['ref'],
        frame_obj['receiver']['ref'],
        argument_vars,
        local_vars)
    return frame

  # def __init__(self, ordinal, location, is_constructor, is_at_return,
  #              function_ref, this_ref, argument_vars, local_vars):
  #   self._ordinal = ordinal
  #   self._location = location
  #   self._is_constructor = is_constructor
  #   self._is_at_return = is_at_return
  #   self._function_ref = function_ref
  #   self._this_ref = this_ref
  #   self._arguments = argument_vars
  #   self._locals = local_vars

  def _handle_break_event(self, recv_obj):
    """Handles a break event from the remote debugger.

    Args:
      recv_obj: JSON object from the packet.
    """
    print 'V8: incoming break event: %s' % (recv_obj)
    body = recv_obj['body']

    # Gather breakpoints
    breakpoint_ids = body.get('breakpoints', [])

    # Fire event
    source = (
        body['script']['name'],
        body['sourceLine'] + 1,
        body['sourceColumn'] + 1)
    event = BreakEvent(self, source, breakpoint_ids)
    if self._break_callback:
      self._break_callback(event)

  def _handle_exception_event(self, recv_obj):
    """Handles an exception event from the remote debugger.

    Args:
      recv_obj: JSON object from the packet.
    """
    print 'V8: incoming exception event: %s' % (recv_obj)
    body = recv_obj['body']

    is_uncaught = body.get('uncaught', False)
    # TODO(benvanik): retype exception?
    exception = body.get('exception', None)

    # Fire event
    source = (
        body['script']['name'],
        body['sourceLine'] + 1,
        body['sourceColumn'] + 1)
    event = ExceptionEvent(self, source, is_uncaught, exception)
    if self._exception_callback:
      self._exception_callback(event)


class _V8ProtocolThread(threading.Thread):
  def __init__(self, protocol, socket, *args, **kwargs):
    super(_V8ProtocolThread, self).__init__(*args, **kwargs)
    self._protocol = protocol
    self._socket = socket
    self._file = socket.makefile('rt')

  def _read_message(self):
    headers = {}
    body = None

    content_length = 0
    while True:
      try:
        line = self._file.readline()
      except socket.error, e:
        if e.errno == 10053:
          # Socket closed by remote host - likely a disconnect
          return None
        print 'V8: network error: %s' % (e)
        return None
      if not line:
        return None
      if line.startswith('Remote debugging session already active'):
        print 'V8: debugger already attached!'
        return None
      if line == '\r\n':
        break
      (key, value) = line.split(':')
      headers[key] = value.strip()
      if key == 'Content-Length':
        content_length = int(headers[key])

    body_obj = None
    if content_length:
      body = self._file.read(content_length)
      if body:
        body_obj = json.loads(body)

    class Message:
      pass
    message = Message()
    message.headers = headers
    message.body = body
    message.body_obj = body_obj
    return message

  def run(self):
    while self._socket:
      message = self._read_message()
      if not message:
        sublime.set_timeout(
            lambda: self._protocol.detach(False, 'Network read error'), 0)
        break
      if message.body_obj:
        self._protocol.queue_recv_from_thread(message.body_obj)
