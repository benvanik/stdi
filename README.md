stdi - Sublime Text 2 Debugger Interface
========================================

A debugger interface for Sublime Text 2, providing an easy way to wire up a
variety of debuggers with rich UI. Included is a debugger for v8.

SUUUUPER experimental! Consider this a proof-of-concept!

## Setup

Clone this repository into your Packages directory.
To find your Packages path, bring up the console with ``ctrl-` `` and enter:

    print sublime.packages_path()

You'll likely need to restart Sublime Text 2 to get the plugin.

## Usage

The debugger requires some settings to function - namely, what you want to debug.
I recommend making these settings per-project, however you can make them global
defaults as well.

From the `Project` menu select `Edit Project`, add or merge the following:

    "settings":
    {
        "debug_target": "v8://localhost:5858"
    }

The provider URI is the target of the debugger. In the future I'll make it more
flexible/add more providers/etc.

When launching your node.js app, add `--debug=5858` to the command line:

    node --debug=5858 my_script.js

Right click in a ST view and select 'Attach Debugger' to start debugging!

More UI/etc is TODO, but for now you can use the Command Palette
(`ctrl-shift-P`) with the prefix `Debugger:` to access most commands. The
following keyboard shortcuts are recognized:

* F5: launch debugger
* shift-F5: attach debugger
* F8: pause/resume target, continue if broken
* F9: add/remove a breakpoint
* shift-F9: enable/disable a breakpoint
* F10: step over next instruction
* F11: step in to next call
* shift-F11: step out of current scope

## Features

### Breakpoints

TODO

### Stack Frame Navigation

TODO

### Watches

TODO

### Expression Evaluation

TODO

### Live Updating on Save

AKA 'edit-and-continue'. This pretty much works right now so long as you don't
make changes that V8 is unable to handle, such as adding/removing functions,
changing scopes, etc. Reporting for failures is TODO.

## Debug Targets

### JavaScript

TODO: support script mapping so DART/coffeescript?/etc work

#### V8/node.js

Working!

* node.js command line: `node --debug=5858 script.js`
* Project setting: `debug_target: "v8://localhost:5858"`

#### Chrome (WebKit?)

Partially implemented; not yet working.

* Chrome command line: `chrome --remote-debugging-port=9222`
* Project setting: `debug_target: "webkit://localhost:9222"`

### Others

It'd be cool to plug in other runtimes that have remote debuggers. It's easy to
add them, so go contribute!

## Resources

* [V8 Debugger Protocol](http://code.google.com/p/v8/wiki/DebuggerProtocol)
* [Chrome Debugger Protocol](https://developers.google.com/chrome-developer-tools/docs/protocol/1.0/debugger)
* [WebKit Protocol](http://code.google.com/p/chromedevtools/wiki/WebKitProtocol)
* [V8 debug-agent.cc](http://v8.googlecode.com/svn/trunk/src/debug-agent.cc)
* [V8 debug-debugger.js](http://v8.googlecode.com/svn/trunk/src/debug-debugger.js)
* [node.js _debugger.js](https://github.com/joyent/node/blob/master/lib/_debugger.js)
* [WebInspector source](http://trac.webkit.org/browser#trunk/Source/WebCore/inspector/)
* [V8 ScriptDebugServer.cpp](http://trac.webkit.org/browser/trunk/Source/WebCore/bindings/v8/ScriptDebugServer.cpp)

## Contributing

Have a fix or feature? Submit a pull request - I love them!

As this is a Google project, you *must* first e-sign the
[Google Contributor License Agreement](http://code.google.com/legal/individual-cla-v1.0.html) before I can accept any
code. It takes only a second and basically just says you won't sue us or claim copyright of your submitted code.

## License

All code except dependencies under third_party/ is licensed under the permissive Apache 2.0 license.
Feel free to fork/rip/etc and use as you wish!

## Credits

Code by [Ben Vanik](http://noxa.org). See [AUTHORS](https://github.com/benvanik/stdi/blob/master/AUTHORS) for additional contributors.
