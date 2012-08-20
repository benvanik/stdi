Debugging Chrome/Safari
=======================

* implement webkit protocol
  * JSON RPC: http://trac.webkit.org/browser/trunk/Source/WebCore/inspector/Inspector.json
  "webSocketDebuggerUrl": "ws://localhost:5899/devtools/page/3_4"

Variable Value Tooltips
=======================

* when selection enters variable range:
  * query variable value, if present:
    * _view_variable_lookup[view.id()] = value/info/etc
    *
  * when moving off value, view.run_command('hide_auto_complete')
    view.run_command('auto_complete', {
        'disable_auto_insert': True,
        'api_completions_only': True,
        'next_completion_if_showing': False,
        'auto_complete_commit_on_tab': True,
        })
* implement EventListener::on_query_completions:
  * return _view_variable_lookup[view.id()]

SourceMaps
==========

* discover source maps:
  * line in file: //@ sourceMappingURL=/path/to/file.js.map
  * HTTP GET url, check header: X-SourceMap: /path/to/file.js.map
* load source maps:
  https://github.com/mozilla/source-map
* SourceMapCache
  * source_maps {} : uri->SourceMap
  * get_original_location(location) -> location
* SourceMap
  * get_original_location(line, column) -> location




* adding things to gutter:
  * breakpoints
    XdebugView
    lookup_view
    https://github.com/Kindari/SublimeXdebug/blob/master/Xdebug.py
  * error/warning/analysis/etc

* messing with lines:
  * highlight
  * underline words (squigglies)
    add_lint_marks
    https://github.com/SublimeLinter/SublimeLinter/blob/master/SublimeLinter.py
    view.add_regions
    view.erase_regions
  * popup at point

* communication with daemon:
  * tcp sockets
    Protocol
    https://github.com/Kindari/SublimeXdebug/blob/master/Xdebug.py
  * async
    https://github.com/quarnster/SublimeClang/blob/master/sublimeclang.py
  * pyv8 to interop with js:
    http://code.google.com/p/pyv8/

* project/files:
  * get file full path/etc
  * get project file is in
  * enumerate project files/root dirs

* settings


sublime.log_commands(False)

views:
use v.settings().set('command_mode', False) on custom views
all keypresses: https://github.com/wuub/SublimePTY/blob/master/Default.sublime-keymap
https://github.com/wuub/SublimePTY/blob/master/process.py
  settings = v.settings()
  settings.set("sublimepty", True)
  settings.set("line_numbers", False)
  settings.set("caret_style", "blink")
  settings.set("auto_complete", False)
  settings.set("draw_white_space", "none")
  settings.set("word_wrap", False)
  settings.set("gutter", False)
  settings.set("color_scheme", os.path.join(PACKAGE_DIR, "SublimePTY.tmTheme"))
  if ON_WINDOWS: # better defaults
      settings.set("font_face", "Consolas Bold")
      settings.set("font_options", ["directwrite"])
      settings.set("font_size", 11)
  v.set_scratch(True)
  v.set_name("TERMINAL")

status bar updates:
- attaching.... attached to xxx
- detached: reason / set timeout(clear)
- stepping... (attached to xxx)
- changing source... (attached to xxx)

StatusBar:
- clear()
- set_default()
- push_message(value, duration?)
- pop_message()


Debugger state:
- ATTACHING
- ATTACHED
- DETACHED
Listener:
- on_attached()
- on_detached(error_message?)
- on_break(location, state_snapshot)
- on_exception(location, state_snapshot)
DebugStateSnapshot:
- active_location()
- frames()
SourceTranslator:
- translate_uri(uri) -> uri or None
DebugController:
- state_snapshot()
- set_state_snapshot(snapshot)
- clear_state_snapshot()
- _set_active_location((uri, line, column))
- _clear_active_location()
- current_frame() = index N
- set_current_frame(n)
DebugView:



STDI:

DiscoveryService:
- register_provider(provider) / unregister_provider(provider)
- get_all_active_instances() -> InstanceInfo[]
- attach_debugger(instance) -> Debugger

InstanceProvider:
- refresh()
- get_active_instances() -> InstanceInfo[]
- attach_debugger(instance) -> Debugger

InstanceInfo:
- provider
- type (extension/page/script/?)
- display_name (page title/?)
- uri (url/startup script path)
- favicon_url (url to favicon/app icon)
- is_attached (true if a debugger is already attached)
+ custom data (pid:processId:routeId)

Debugger:
- provider
- instance_info
- version_info
- breakpoints
- watchers
- detach()
- is_running()
- start() / can_start()
- restart() / can_restart()
- stop() / can_stop()
- pause() / can_pause()
- continue() / can_continue()
- step_next(count=1) / can_step_next()
- step_in(count=1) / can_step_in()
- step_out(count=1) / can_step_out()
- evaluate(expr, frame, global, disable_break, handles) -> result
  - handles: [{"name": "foo", "handle": 25}], expr: "foo.toString()"
- query_stacktrace(from_frame, to_frame, bottom) -> Frames[] ?
- query_object(handle) -> object
- query_objects(handles) -> object[]
- force_gc()
- change_source(url, new_source) -> failed?
  - http://v8.googlecode.com/svn/trunk/src/debug-debugger.js
  - DebugCommandProcessor.prototype.changeLiveRequest
  - stepin_recommended, change_log, result

Frame:
- index
- receiver ?
- func ?
- script
- is_constructor
- is_debugger_frame
- arguments[] : {name: str (unless anon), value: value}
- locals[] : {name, value}
- position: src pos
- line
- column
- source_line_text
- scopes[]

Scope:
- frame
- index
- type : global / local / with / closure / catch
- object

BreakpointList:
- debugger
- get_all_breakpoints() -> Breakpoint[]
- get_breakpoints_for_location(url, line?, column?) -> Breakpoint[]
- set_breakpoint_at_location(url, line, column) -> Breakpoint
- set_breakpoint_at_function(function_name) -> Breakpoint
- clear_breakpoint(breakpoint)
- clear_breakpoints_for_location(url)
- clear_all_breakpoints()
- exception_breakpoint_mode() / set_exception_breakpoint_mode() : all / uncaught

Breakpoint:
- (url, line, column) or function_name
- display_name() / set_display_name()
- is_enabled() / set_enabled()
- condition() / set_condition()
- ignore_count() / set_ignore_count()

WatcherList:
- debugger
- get_all_watchers() -> Watcher[]
- set_watcher(expr) -> Watcher
- clear_watcher(watcher)
- clear_all_watchers()

Watcher:
- expr

DebugEvent:
- debugger
- source_line
- source_column
- source_line_text
- script??

BreakEvent(DebugEvent):
- invocation_text
- breakpoints[]

ExceptionEvent(DebugEvent):
- is_uncaught
- exception
