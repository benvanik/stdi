stdi - Sublime Text 2 Debugger Interface
========================================

A debugger interface for Sublime Text 2, providing an easy way to wire up a
variety of debuggers with rich UI. Included is a debugger for v8.

## Usage

TODO

## Setup

Clone this repository into your Packages directory.
To find your Packages path, bring up the console with ``ctrl-` `` and enter:

    print sublime.packages_path()

### Project Setup

The debugger requires some settings to function - namely, what you want to debug.
I recommend making these settings per-project, however you can make them global
defaults as well.

From the `Project` menu select `Edit Project`, add the following (or merge):

    "settings":
    {
        "stdi_provider": "v8://localhost:5898"
    }

The provider URI is the target of the debugger. In the future I'll make it more flexible/add more/etc.

When launching your node.js app, add `--debug=5898` to the command line:

    node --debug=5898 my_script.js

Right click in a view and select 'Attach Debugger' to start debugging!

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
